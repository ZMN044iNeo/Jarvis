#!/usr/bin/env python3
"""
Moonraker API Skill for Klipper 3D Printing Assistant.

Provides a Python client class and CLI tool for interacting with Moonraker
REST API endpoints, including status monitoring, job control, file management,
webcams, power devices, history, and Gcode execution.
"""

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union


class MoonrakerError(Exception):
    """Custom exception class for Moonraker API operations."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_type: str = "MoonrakerError",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception details into a standard dictionary format."""
        res: Dict[str, Any] = {
            "success": False,
            "error": {
                "type": self.error_type,
                "message": self.message,
            },
        }
        if self.status_code is not None:
            res["error"]["status_code"] = self.status_code
        if self.details:
            res["error"]["details"] = self.details
        return res


class MoonrakerAPI:
    """Client for Moonraker REST API."""

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ):
        """
        Initialize the Moonraker client.

        :param url: Moonraker base URL (defaults to MOONRAKER_URL env or http://localhost:7125)
        :param api_key: Moonraker API key (defaults to MOONRAKER_API_KEY env)
        :param timeout: Request timeout in seconds
        """
        raw_url = url or os.environ.get("MOONRAKER_URL") or "http://localhost:7125"
        if not raw_url.startswith("http://") and not raw_url.startswith("https://"):
            raw_url = f"http://{raw_url}"
        self.url = raw_url.rstrip("/")

        self.api_key = api_key or os.environ.get("MOONRAKER_API_KEY")
        self.timeout = timeout

    def _get_headers(self, custom_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Build standard headers including authorization if configured."""
        headers = {
            "User-Agent": "Moonraker-Python-Skill/1.0",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        if custom_headers:
            headers.update(custom_headers)
        return headers

    def _encode_multipart(
        self, fields: Dict[str, str], files: Dict[str, Tuple[str, bytes, str]]
    ) -> Tuple[bytes, str]:
        """
        Build multipart/form-data request body without external libraries.

        :param fields: Text form fields {name: value}
        :param files: File form fields {field_name: (filename, bytes_data, content_type)}
        """
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
        body = bytearray()

        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
            body.extend(f"{value}\r\n".encode("utf-8"))

        for key, (filename, content_bytes, content_type) in files.items():
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(
                f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode(
                    "utf-8"
                )
            )
            body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
            body.extend(content_bytes)
            body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode("utf-8"))
        content_type_header = f"multipart/form-data; boundary={boundary}"
        return bytes(body), content_type_header

    def _request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Any] = None,
        custom_headers: Optional[Dict[str, str]] = None,
        raw_query_string: Optional[str] = None,
        multipart_files: Optional[Dict[str, Tuple[str, bytes, str]]] = None,
        multipart_fields: Optional[Dict[str, str]] = None,
    ) -> Any:
        """
        Execute an HTTP request to Moonraker with detailed error handling.
        """
        path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        full_url = f"{self.url}{path}"

        if raw_query_string:
            full_url = f"{full_url}?{raw_query_string}"
        elif params:
            query_str = urllib.parse.urlencode(params)
            full_url = f"{full_url}?{query_str}"

        headers = self._get_headers(custom_headers)
        body_data: Optional[bytes] = None

        if multipart_files:
            fields = multipart_fields or {}
            body_data, content_type = self._encode_multipart(fields, multipart_files)
            headers["Content-Type"] = content_type
        elif json_data is not None:
            headers["Content-Type"] = "application/json"
            body_data = json.dumps(json_data).encode("utf-8")

        req = urllib.request.Request(full_url, data=body_data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                resp_bytes = response.read()
                content_type = response.headers.get("Content-Type", "")

                if "application/json" in content_type or path.startswith(
                    ("/printer", "/server", "/machine", "/access")
                ):
                    try:
                        data = json.loads(resp_bytes.decode("utf-8"))
                        if isinstance(data, dict) and "result" in data:
                            return data["result"]
                        return data
                    except json.JSONDecodeError:
                        return resp_bytes.decode("utf-8", errors="replace")
                else:
                    return resp_bytes

        except urllib.error.HTTPError as e:
            error_body = ""
            parsed_error = None
            try:
                error_body = e.read().decode("utf-8", errors="replace")
                parsed_error = json.loads(error_body)
            except Exception:
                pass

            msg = f"HTTP {e.code} {e.reason}"
            if isinstance(parsed_error, dict):
                if "error" in parsed_error:
                    err_val = parsed_error["error"]
                    if isinstance(err_val, dict) and "message" in err_val:
                        msg += f": {err_val['message']}"
                    elif isinstance(err_val, str):
                        msg += f": {err_val}"
                elif "message" in parsed_error:
                    msg += f": {parsed_error['message']}"

            details = {
                "url": full_url,
                "method": method,
                "raw_response": error_body or None,
            }

            if e.code in (401, 403):
                msg += " (Check MOONRAKER_API_KEY)"

            raise MoonrakerError(
                message=msg, status_code=e.code, error_type="HTTPError", details=details
            ) from e

        except urllib.error.URLError as e:
            reason_str = str(e.reason)
            msg = f"Failed to connect to Moonraker at {self.url}: {reason_str}"
            details = {"url": full_url, "method": method, "reason": reason_str}
            raise MoonrakerError(
                message=msg, error_type="ConnectionError", details=details
            ) from e

        except TimeoutError as e:
            msg = f"Request timed out after {self.timeout}s connecting to {full_url}"
            details = {"url": full_url, "method": method, "timeout": self.timeout}
            raise MoonrakerError(
                message=msg, error_type="TimeoutError", details=details
            ) from e

        except Exception as e:
            msg = f"Unexpected error executing {method} {full_url}: {str(e)}"
            raise MoonrakerError(message=msg, error_type="UnexpectedError") from e

    # --- 1. Printer Info & Status ---

    def get_printer_info(self) -> Dict[str, Any]:
        """GET /printer/info - Retrieve basic printer information and Klipper state."""
        return self._request("/printer/info", method="GET")

    def query_printer_objects(
        self, objects: Optional[Union[List[str], Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        GET /printer/objects/query - Query printer objects.

        :param objects: List of object names or dict of query keys
        """
        if objects is None:
            objects = [
                "heater_bed",
                "extruder",
                "print_stats",
                "toolhead",
                "gcode_move",
                "display_status",
            ]

        if isinstance(objects, (list, tuple, set)):
            raw_qs = "&".join(urllib.parse.quote(obj) for obj in objects)
            return self._request("/printer/objects/query", method="GET", raw_query_string=raw_qs)
        elif isinstance(objects, dict):
            return self._request("/printer/objects/query", method="GET", params=objects)
        else:
            raise MoonrakerError("Objects query parameter must be a list, dict, or None")

    def get_print_stats(self) -> Dict[str, Any]:
        """GET /printer/objects/query?print_stats - Get print statistics and job status."""
        res = self._request("/printer/objects/query", method="GET", raw_query_string="print_stats")
        if isinstance(res, dict) and "status" in res:
            return res["status"].get("print_stats", {})
        return res

    def get_status(self) -> Dict[str, Any]:
        """
        Get full consolidated printer status (temperatures, position, print progress, printer state).
        """
        info = self.get_printer_info()
        objects_res = self.query_printer_objects([
            "heater_bed",
            "extruder",
            "print_stats",
            "toolhead",
            "gcode_move",
            "display_status",
        ])

        status_objs = {}
        if isinstance(objects_res, dict) and "status" in objects_res:
            status_objs = objects_res["status"]

        extruder = status_objs.get("extruder", {})
        heater_bed = status_objs.get("heater_bed", {})
        print_stats = status_objs.get("print_stats", {})
        toolhead = status_objs.get("toolhead", {})
        gcode_move = status_objs.get("gcode_move", {})
        display_status = status_objs.get("display_status", {})

        position = toolhead.get("position") or gcode_move.get("gcode_position") or [0, 0, 0, 0]

        summary = {
            "state": info.get("state", "unknown"),
            "state_message": info.get("state_message", ""),
            "hostname": info.get("hostname", ""),
            "klipper_path": info.get("klipper_path", ""),
            "temperatures": {
                "extruder": {
                    "actual": extruder.get("temperature", 0.0),
                    "target": extruder.get("target", 0.0),
                    "power": extruder.get("power", 0.0),
                },
                "heater_bed": {
                    "actual": heater_bed.get("temperature", 0.0),
                    "target": heater_bed.get("target", 0.0),
                    "power": heater_bed.get("power", 0.0),
                },
            },
            "position": {
                "x": position[0] if len(position) > 0 else 0.0,
                "y": position[1] if len(position) > 1 else 0.0,
                "z": position[2] if len(position) > 2 else 0.0,
                "e": position[3] if len(position) > 3 else 0.0,
            },
            "print_progress": {
                "filename": print_stats.get("filename", ""),
                "state": print_stats.get("state", "standby"),
                "progress": display_status.get(
                    "progress", print_stats.get("progress", 0.0)
                ),
                "print_duration": print_stats.get("print_duration", 0.0),
                "total_duration": print_stats.get("total_duration", 0.0),
                "filament_used": print_stats.get("filament_used", 0.0),
                "message": print_stats.get("message", ""),
            },
            "raw_info": info,
            "raw_objects": status_objs,
        }
        return summary

    # --- 2. Gcode & Job Control ---

    def send_gcode(self, script: str) -> Dict[str, Any]:
        """
        POST /printer/gcode/script - Send a Gcode command to Klipper.

        :param script: Gcode command or string
        """
        return self._request("/printer/gcode/script", method="POST", json_data={"script": script})

    def start_print(self, filename: str) -> Dict[str, Any]:
        """
        POST /printer/print/start?filename=<name> - Start printing a Gcode file.
        """
        quoted_filename = urllib.parse.quote(filename)
        try:
            return self._request(
                f"/printer/print/start?filename={quoted_filename}", method="POST"
            )
        except MoonrakerError as e:
            if e.status_code == 404:
                return self._request(
                    f"/print/start?filename={quoted_filename}", method="POST"
                )
            raise

    def pause_print(self) -> Dict[str, Any]:
        """POST /printer/print/pause - Pause current print."""
        try:
            return self._request("/printer/print/pause", method="POST")
        except MoonrakerError as e:
            if e.status_code == 404:
                return self._request("/print/pause", method="POST")
            raise

    def resume_print(self) -> Dict[str, Any]:
        """POST /printer/print/resume - Resume paused print."""
        try:
            return self._request("/printer/print/resume", method="POST")
        except MoonrakerError as e:
            if e.status_code == 404:
                return self._request("/print/resume", method="POST")
            raise

    def cancel_print(self) -> Dict[str, Any]:
        """POST /printer/print/cancel - Cancel current print."""
        try:
            return self._request("/printer/print/cancel", method="POST")
        except MoonrakerError as e:
            if e.status_code == 404:
                return self._request("/print/cancel", method="POST")
            raise

    def emergency_stop(self) -> Dict[str, Any]:
        """POST /printer/emergency_stop - Send emergency stop (M112)."""
        return self._request("/printer/emergency_stop", method="POST")

    # --- 3. File Operations ---

    def list_files(self, root: str = "gcodes") -> Dict[str, Any]:
        """GET /server/files/list?root=gcodes - List files on the server."""
        return self._request("/server/files/list", method="GET", params={"root": root})

    def upload_file(
        self,
        filepath: str,
        root: str = "gcodes",
        print_after_upload: bool = False,
    ) -> Dict[str, Any]:
        """
        POST /server/files/upload - Upload a Gcode file to Moonraker.

        :param filepath: Local path to the file
        :param root: Storage root (default: 'gcodes')
        :param print_after_upload: Automatically start print after upload
        """
        if not os.path.isfile(filepath):
            raise MoonrakerError(f"Local file not found: {filepath}", error_type="FileNotFound")

        filename = os.path.basename(filepath)
        mime_type, _ = mimetypes.guess_type(filepath)
        if not mime_type:
            mime_type = "application/octet-stream"

        with open(filepath, "rb") as f:
            content_bytes = f.read()

        multipart_files = {
            "file": (filename, content_bytes, mime_type)
        }
        multipart_fields = {
            "root": root,
            "print": "true" if print_after_upload else "false"
        }

        return self._request(
            "/server/files/upload",
            method="POST",
            multipart_files=multipart_files,
            multipart_fields=multipart_fields,
        )

    def download_file(
        self,
        filename: str,
        root: str = "gcodes",
        dest_path: Optional[str] = None,
    ) -> Union[bytes, str]:
        """
        GET /server/files/gcodes/<filename> - Download file from server.

        :param filename: Remote file path relative to root
        :param root: Root directory (default: 'gcodes')
        :param dest_path: Optional local path to save the downloaded file
        """
        clean_filename = filename.lstrip("/")
        quoted_path = urllib.parse.quote(clean_filename)
        endpoint = f"/server/files/{root}/{quoted_path}"

        raw_data = self._request(endpoint, method="GET")

        if isinstance(raw_data, str):
            data_bytes = raw_data.encode("utf-8")
        elif isinstance(raw_data, bytes):
            data_bytes = raw_data
        else:
            data_bytes = json.dumps(raw_data).encode("utf-8")

        if dest_path:
            dest_dir = os.path.dirname(dest_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(data_bytes)
            return os.path.abspath(dest_path)

        return raw_data

    # --- 4. Server & Hardware Info ---

    def get_server_info(self) -> Dict[str, Any]:
        """GET /server/info - Get Moonraker server information."""
        return self._request("/server/info", method="GET")

    def list_webcams(self) -> Dict[str, Any]:
        """GET /server/webcams/list - Get webcam configurations and stream info."""
        return self._request("/server/webcams/list", method="GET")

    def get_power_devices(self) -> Dict[str, Any]:
        """GET /machine/device_power/devices - Get power devices and status."""
        return self._request("/machine/device_power/devices", method="GET")

    def set_power_device(self, device: str, action: str) -> Dict[str, Any]:
        """
        POST /machine/device_power/device - Control power device.

        :param device: Device name
        :param action: 'on', 'off', or 'toggle'
        """
        clean_action = action.lower()
        if clean_action not in ("on", "off", "toggle"):
            raise MoonrakerError(
                f"Invalid power action '{action}'. Must be 'on', 'off', or 'toggle'."
            )
        return self._request(
            "/machine/device_power/device",
            method="POST",
            json_data={"device": device, "action": clean_action},
        )

    def get_history(
        self,
        limit: int = 50,
        start: int = 0,
        order: str = "desc",
    ) -> Dict[str, Any]:
        """
        GET /server/history/list - Get job history.

        :param limit: Max number of history items
        :param start: Starting index offset
        :param order: Sort order ('asc' or 'desc')
        """
        params = {"limit": limit, "start": start, "order": order}
        return self._request("/server/history/list", method="GET", params=params)

    def get_notifications(self) -> Dict[str, Any]:
        """GET /server/notifications - Get system notifications."""
        try:
            return self._request("/server/notifications", method="GET")
        except MoonrakerError as e:
            if e.status_code == 404:
                return self._request("/server/announcements/list", method="GET")
            raise

    def get_temperature_presets(self) -> Dict[str, Any]:
        """GET /server/temperature_presets - Get temperature presets."""
        return self._request("/server/temperature_presets", method="GET")

    def get_combined_info(self) -> Dict[str, Any]:
        """Get combined server and printer info."""
        server_info = self.get_server_info()
        printer_info = self.get_printer_info()
        return {
            "server_info": server_info,
            "printer_info": printer_info,
        }


def main() -> None:
    """CLI entrypoint for the Moonraker API skill."""
    parser = argparse.ArgumentParser(
        description="Moonraker API skill for 3D printer management.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 moonraker_api.py --status
  python3 moonraker_api.py --info
  python3 moonraker_api.py --send "G28"
  python3 moonraker_api.py --start "bench3d.gcode"
  python3 moonraker_api.py --pause
  python3 moonraker_api.py --resume
  python3 moonraker_api.py --cancel
  python3 moonraker_api.py --estop
  python3 moonraker_api.py --files
  python3 moonraker_api.py --upload "./cube.gcode"
  python3 moonraker_api.py --webcams
  python3 moonraker_api.py --power printer_switch on
  python3 moonraker_api.py --jobs
        """,
    )

    parser.add_argument("--url", help="Moonraker server URL (overrides MOONRAKER_URL env)")
    parser.add_argument("--api-key", help="Moonraker API key (overrides MOONRAKER_API_KEY env)")
    parser.add_argument(
        "--timeout", type=float, default=10.0, help="Request timeout in seconds (default: 10.0)"
    )

    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--status", action="store_true", help="Get full printer status (temps, position, progress)"
    )
    action_group.add_argument("--send", metavar="GCODE", help="Send a Gcode command to printer")
    action_group.add_argument("--start", metavar="FILENAME", help="Start printing a file")
    action_group.add_argument("--pause", action="store_true", help="Pause current print")
    action_group.add_argument("--resume", action="store_true", help="Resume paused print")
    action_group.add_argument("--cancel", action="store_true", help="Cancel current print")
    action_group.add_argument("--estop", action="store_true", help="Emergency stop printer")
    action_group.add_argument("--files", action="store_true", help="List Gcode files")
    action_group.add_argument("--upload", metavar="FILEPATH", help="Upload a Gcode file")
    action_group.add_argument(
        "--download", metavar="FILENAME", help="Download a file from server"
    )
    action_group.add_argument("--webcams", action="store_true", help="List webcams")
    action_group.add_argument(
        "--power",
        nargs="*",
        metavar=("DEVICE", "ACTION"),
        help="Control power device (e.g. '--power printer on', or no args to list)",
    )
    action_group.add_argument("--jobs", action="store_true", help="List print history/jobs")
    action_group.add_argument("--info", action="store_true", help="Get server and printer info")
    action_group.add_argument(
        "--notifications", action="store_true", help="Get server notifications"
    )
    action_group.add_argument(
        "--presets", action="store_true", help="Get temperature presets"
    )

    parser.add_argument(
        "--output", metavar="PATH", help="Destination path for file download"
    )

    args = parser.parse_args()

    # Create API client instance
    client = MoonrakerAPI(url=args.url, api_key=args.api_key, timeout=args.timeout)

    result: Dict[str, Any] = {}

    try:
        if args.status:
            result = {"success": True, "data": client.get_status()}
        elif args.send:
            res = client.send_gcode(args.send)
            result = {"success": True, "result": res}
        elif args.start:
            res = client.start_print(args.start)
            result = {"success": True, "result": res}
        elif args.pause:
            res = client.pause_print()
            result = {"success": True, "result": res}
        elif args.resume:
            res = client.resume_print()
            result = {"success": True, "result": res}
        elif args.cancel:
            res = client.cancel_print()
            result = {"success": True, "result": res}
        elif args.estop:
            res = client.emergency_stop()
            result = {"success": True, "result": res}
        elif args.files:
            res = client.list_files()
            result = {"success": True, "result": res}
        elif args.upload:
            res = client.upload_file(args.upload)
            result = {"success": True, "result": res}
        elif args.download:
            dl_res = client.download_file(args.download, dest_path=args.output)
            result = {"success": True, "result": dl_res}
        elif args.webcams:
            res = client.list_webcams()
            result = {"success": True, "result": res}
        elif args.power is not None:
            if len(args.power) == 0:
                res = client.get_power_devices()
                result = {"success": True, "result": res}
            elif len(args.power) == 2:
                device, action = args.power[0], args.power[1]
                res = client.set_power_device(device, action)
                result = {"success": True, "result": res}
            elif len(args.power) == 1 and args.power[0].lower() == "list":
                res = client.get_power_devices()
                result = {"success": True, "result": res}
            else:
                raise MoonrakerError(
                    "Invalid --power arguments. Usage: --power [DEVICE ACTION] or --power"
                )
        elif args.jobs:
            res = client.get_history()
            result = {"success": True, "result": res}
        elif args.info:
            res = client.get_combined_info()
            result = {"success": True, "result": res}
        elif args.notifications:
            res = client.get_notifications()
            result = {"success": True, "result": res}
        elif args.presets:
            res = client.get_temperature_presets()
            result = {"success": True, "result": res}
        else:
            # Default to status if no action specified
            result = {"success": True, "data": client.get_status()}

    except MoonrakerError as e:
        result = e.to_dict()
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        sys.exit(1)
    except Exception as e:
        err = MoonrakerError(message=f"Unhandled error: {str(e)}", error_type="UnhandledError")
        result = err.to_dict()
        sys.stdout.write(json.dumps(result, indent=2) + "\n")
        sys.exit(1)

    sys.stdout.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
