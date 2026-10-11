"""Browser flow checks on synthetic-only UI fixtures, never project approvals."""

import argparse
import json
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import httpx
from websockets.sync.client import connect

from regintel.mapping.review_screen import render


class CDP:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0

    def call(self, method, params=None):
        self.sequence += 1
        identifier = self.sequence
        self.socket.send(
            json.dumps({"id": identifier, "method": method, "params": params or {}})
        )
        while True:
            response = json.loads(self.socket.recv(timeout=10))
            if response.get("id") == identifier:
                if "error" in response:
                    raise RuntimeError(response["error"]["message"])
                return response.get("result", {})

    def evaluate(self, expression):
        result = self.call(
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True, "awaitPromise": True},
        )
        if "exceptionDetails" in result:
            raise RuntimeError(
                "Browser evaluation failed: " + str(result["exceptionDetails"])
            )
        return result["result"].get("value")


def wait_for(check, message, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(message)


def run(root, browser):
    directory = root / (".review-flow-" + uuid4().hex)
    directory.mkdir()
    downloads = directory / "downloads"
    downloads.mkdir()
    fixture = {
        "schema_version": 1,
        "synthetic": True,
        "queries": [
            {"scenario_id": f"UNIT-probe-{i}", "query": f"SYNTHETIC TEST QUERY {i}"}
            for i in range(6)
        ],
        "records": [
            {
                "id": f"UNIT-{i:03d}",
                "text": f"SYNTHETIC TEST EVIDENCE {i:03d} — not regulatory text",
                "content_hash": "unit-fixture",
                "start_page": 1,
                "end_page": 1,
            }
            for i in range(500)
        ],
        "sources": {
            "unit-fixture": {
                "title": "SYNTHETIC UI TEST FIXTURE",
                "source_url": "https://www.rbi.org.in/",
            }
        },
    }
    page = directory / "synthetic_review_fixture.html"
    page.write_text(render(fixture), encoding="utf-8")
    profile = directory / "browser_profile"
    process = subprocess.Popen(
        [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-extensions",
            "--proxy-server=127.0.0.1:9",
            "--remote-debugging-port=0",
            "--user-data-dir=" + str(profile),
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    checks = []
    try:
        active_port = profile / "DevToolsActivePort"
        wait_for(lambda: active_port.exists(), "Browser did not start", timeout=20)
        port = int(active_port.read_text().splitlines()[0])
        with httpx.Client(trust_env=False, timeout=5) as client:
            targets = client.get(f"http://127.0.0.1:{port}/json/list").json()
        target = next(t for t in targets if t["type"] == "page")
        with connect(
            target["webSocketDebuggerUrl"], proxy=None, open_timeout=5
        ) as socket:
            cdp = CDP(socket)
            cdp.call("Page.enable")
            cdp.call(
                "Browser.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": str(downloads)},
            )
            cdp.call("Page.navigate", {"url": page.as_uri()})
            wait_for(
                lambda: (
                    cdp.evaluate(
                        "document.querySelectorAll('#candidates article').length"
                    )
                    == 25
                ),
                "Initial page did not render",
            )
            assert "0/6" in cdp.evaluate(
                "document.getElementById('status').textContent"
            )
            checks.append("Initial six queries pending; 25 of 500 candidates displayed")

            cdp.evaluate("document.getElementById('next').click()")
            assert "UNIT-025" in cdp.evaluate(
                "document.querySelector('#candidates article label').textContent"
            )
            cdp.evaluate(
                "document.getElementById('search').value='UNIT-499'; document.getElementById('search').dispatchEvent(new Event('input'))"
            )
            assert (
                cdp.evaluate("document.querySelectorAll('#candidates article').length")
                == 1
            )
            cdp.evaluate("document.querySelector('#candidates input').click()")
            assert "1 selected" in cdp.evaluate(
                "document.getElementById('status').textContent"
            )
            checks.append("Paging, search and candidate selection")

            cdp.evaluate("document.getElementById('export').click()")
            assert "explicitly" in cdp.evaluate(
                "document.getElementById('message').textContent"
            )
            assert not (downloads / "reviewed_relevance.json").exists()
            checks.append("Pending cases block completed-label download")

            cdp.evaluate("document.getElementById('draft').click()")
            draft_path = downloads / "relevance_draft.json"
            wait_for(lambda: draft_path.exists(), "Draft did not download")
            draft = json.loads(draft_path.read_text())
            assert draft["cases"][0]["relevant_section_ids"] == ["UNIT-499"]
            assert all(c["review_status"] == "pending" for c in draft["cases"])
            checks.append(
                "Actual draft JSON download preserves selection and pending states"
            )

            def field(identifier, value):
                cdp.evaluate(
                    f"document.getElementById({json.dumps(identifier)}).value={json.dumps(value)}; document.getElementById({json.dumps(identifier)}).dispatchEvent(new Event('input'))"
                )

            for index in range(6):
                cdp.evaluate(
                    f"document.getElementById('query').value='{index}'; document.getElementById('query').dispatchEvent(new Event('change'))"
                )
                field("reviewer", "SYNTHETIC BROWSER TEST — NOT A HUMAN REVIEW")
                field("rationale", "Fixture-only browser interaction verification")
                field(
                    "answerability",
                    "relevant_documents_present"
                    if index == 0
                    else "no_relevant_document_in_subset",
                )
                cdp.evaluate(
                    "document.getElementById('full-corpus').click(); document.getElementById('approve').click()"
                )
            assert "6/6" in cdp.evaluate(
                "document.getElementById('status').textContent"
            )
            cdp.evaluate("document.getElementById('export').click()")
            complete_path = downloads / "reviewed_relevance.json"
            wait_for(
                lambda: complete_path.exists(),
                "Completed fixture labels did not download",
            )
            complete = json.loads(complete_path.read_text())
            assert all(
                c["review_status"] == "approved"
                and c["scenario_id"].startswith("UNIT-")
                for c in complete["cases"]
            )
            checks.append(
                "Actual completed JSON download for synthetic fixture decisions only"
            )

            cdp.call("DOM.enable")
            node_id = cdp.call(
                "DOM.querySelector",
                {
                    "nodeId": cdp.call("DOM.getDocument")["root"]["nodeId"],
                    "selector": "#import",
                },
            )["nodeId"]
            cdp.call(
                "DOM.setFileInputFiles",
                {"nodeId": node_id, "files": [str(complete_path)]},
            )
            wait_for(
                lambda: (
                    "restored"
                    in cdp.evaluate("document.getElementById('message').textContent")
                ),
                "Draft restoration failed",
            )
            assert "0/6" in cdp.evaluate(
                "document.getElementById('status').textContent"
            )
            cdp.evaluate(
                "document.getElementById('query').value='0'; document.getElementById('query').dispatchEvent(new Event('change'))"
            )
            assert "1 selected" in cdp.evaluate(
                "document.getElementById('status').textContent"
            )
            assert cdp.evaluate("document.getElementById('reviewer').value").startswith(
                "SYNTHETIC"
            )
            checks.append(
                "Real file-input restoration resets all fixture approvals and preserves decisions"
            )

            stale = dict(draft)
            stale["packet_sha256"] = "wrong-packet"
            stale_path = directory / "stale_fixture.json"
            stale_path.write_text(json.dumps(stale))
            cdp.call(
                "DOM.setFileInputFiles", {"nodeId": node_id, "files": [str(stale_path)]}
            )
            wait_for(
                lambda: (
                    "another packet"
                    in cdp.evaluate("document.getElementById('message').textContent")
                ),
                "Stale draft not rejected",
            )
            assert "1 selected" in cdp.evaluate(
                "document.getElementById('status').textContent"
            )
            checks.append("Stale draft rejected without changing current selection")
            cdp.evaluate("document.getElementById('approve').click()")
            assert "1/6" in cdp.evaluate(
                "document.getElementById('status').textContent"
            )
            field("rationale", "Changed synthetic test rationale")
            assert "0/6" in cdp.evaluate(
                "document.getElementById('status').textContent"
            )
            checks.append("Editing a reviewed fixture case invalidates its approval")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    return {
        "schema_version": 1,
        "browser": "Edge headless",
        "checks": checks,
        "synthetic_only": True,
        "actual_project_approvals_created": 0,
        "fixture_directory": directory.relative_to(root).as_posix(),
        "notice": "Downloaded approvals are clearly synthetic UI test fixtures, not project relevance labels. No database or real review artifacts changed.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--browser",
        type=Path,
        default=Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Preserve existing browser result")
    result = run(Path.cwd().resolve(), args.browser)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
