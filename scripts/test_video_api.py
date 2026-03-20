#!/usr/bin/env python3
"""
Quick smoke test for OpenAI-compatible video understanding APIs.

Reads OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_MODEL from .env or environment,
then sends a local video path with different block formats to identify which
format your provider accepts.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_VIDEO_PATH = (
    "/Users/vichen/school/MCP/task分工/4_Offline Video 2 (35)/data/"
    "video_operation/multi_video/task_sample/BCS_video/Better_Call_Saul_1.mp4"
)


def _client_from_env() -> tuple[OpenAI, str, str]:
    # Use .env as source of truth for this debugging script.
    load_dotenv(override=True)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip() or "qwen-vl-max-latest"

    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    if not base_url:
        raise RuntimeError("Missing OPENAI_BASE_URL")

    return OpenAI(api_key=api_key, base_url=base_url), model, base_url


def _run_case(client: OpenAI, model: str, case_name: str, video_path: Path, block: dict[str, Any]) -> None:
    print(f"\n=== Case: {case_name} ===")
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Please describe this video in one sentence and answer "
                                "whether there is a person wearing glasses. "
                                "Return JSON: {\"summary\":\"...\",\"has_glasses\":true/false}."
                            ),
                        },
                        block,
                    ],
                }
            ],
        )
        message = resp.choices[0].message
        print("SUCCESS")
        print("raw_content:", message.content)
        if getattr(message, "tool_calls", None):
            print("tool_calls:", message.tool_calls)
    except Exception as exc:  # noqa: BLE001
        print("FAILED")
        print(f"{type(exc).__name__}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test video input format for OpenAI-compatible API.")
    parser.add_argument("--video", type=str, default=DEFAULT_VIDEO_PATH, help="Local video file path.")
    args = parser.parse_args()

    video_path = Path(args.video).expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    client, model, base_url = _client_from_env()
    print("Using model:", model)
    print("Using base_url:", base_url)
    print("Video:", str(video_path))
    print("Video size (MB):", round(video_path.stat().st_size / (1024 * 1024), 2))

    file_url = f"file://{video_path}"
    video_data_uri = "data:video/mp4;base64," + base64.b64encode(video_path.read_bytes()).decode("ascii")

    # Case 1: common OpenAI-compatible style used in your current MCPU flow.
    _run_case(
        client=client,
        model=model,
        case_name="type=video_url",
        video_path=video_path,
        block={"type": "video_url", "video_url": {"url": file_url}},
    )

    # Case 2: some compatible APIs use "input_video" block style.
    _run_case(
        client=client,
        model=model,
        case_name="type=input_video",
        video_path=video_path,
        block={"type": "input_video", "input_video": {"url": file_url}},
    )

    # Case 3: video_url with data URI.
    _run_case(
        client=client,
        model=model,
        case_name="type=video_url(data_uri)",
        video_path=video_path,
        block={"type": "video_url", "video_url": {"url": video_data_uri}},
    )

    # Case 4: native "video" block (some providers support this).
    _run_case(
        client=client,
        model=model,
        case_name="type=video(data_uri_string)",
        video_path=video_path,
        block={"type": "video", "video": video_data_uri},
    )

    # Case 5: native "video" block with url object variant.
    _run_case(
        client=client,
        model=model,
        case_name="type=video(data_uri_object)",
        video_path=video_path,
        block={"type": "video", "video": {"url": video_data_uri}},
    )

    print("\nDone.")
    print("If both cases fail with schema errors, the provider likely does not accept local file:// video URLs.")
    print("In that case, you need either:")
    print("1) an HTTP-accessible video URL, or")
    print("2) provider-specific file upload API before referencing the uploaded file.")


if __name__ == "__main__":
    main()
