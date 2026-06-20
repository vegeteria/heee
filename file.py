import base64
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import requests

APP_PASSWORD = "oAR80SGuX3EEjUGFRwLFKBTiris="


@dataclass
class SportzxChannel:
    event_title: str
    event_id: str
    event_cat: str
    event_name: str
    channel_title: Optional[str] = None
    stream_url: str = ""
    keyid: Optional[str] = None
    key: Optional[str] = None
    api: Optional[str] = None
    headers: Optional[str] = None
    referer: Optional[str] = None
    origin: Optional[str] = None
    team_a_flag: Optional[str] = None
    team_b_flag: Optional[str] = None
    channel_logo: Optional[str] = None
    start_time_gmt: str = ""
    end_time_gmt: str = ""


class SportzxClient:

    def __init__(self, excluded_categories: List[str] = None, timeout: int = 12):
        self.excluded_categories = set(c.lower() for c in (excluded_categories or []))
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Dalvik/2.1.0 (Linux; Android 13)",
                "Accept-Encoding": "gzip",
            }
        )

        with open("raw.txt", "w", encoding="utf-8") as f:
            f.write("=== SPORTZX RAW DECRYPTED DATA DUMP ===\n\n")

    def _generate_aes_key_iv(self, s: str) -> tuple[bytes, bytes]:
        CHARSET = (
            b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+!@#$%&="
        )

        def u32(x: int) -> int:
            return x & 0xFFFFFFFF

        data = s.encode("utf-8")
        n = len(data)

        u = 0x811C9DC5
        for b in data:
            u = u32((u ^ b) * 0x1000193)

        key = bytearray(16)
        for i in range(16):
            b = data[i % n]
            u = u32(u * 0x1F + (i ^ b))
            key[i] = CHARSET[u % len(CHARSET)]

        u = 0x811C832A
        for b in data:
            u = u32((u ^ b) * 0x1000193)

        iv = bytearray(16)
        idx = 0
        acc = 0
        while idx != 0x30:
            b = data[idx % n]
            u = u32(u * 0x1D + (acc ^ b))
            iv[idx // 3] = CHARSET[u % len(CHARSET)]
            idx += 3
            acc = u32(acc + 7)

        return bytes(key), bytes(iv)

    def _decrypt_data(self, b64_data: str) -> str:
        if not b64_data.strip():
            return ""

        try:
            ct = base64.b64decode(b64_data)
            key, iv = self._generate_aes_key_iv(APP_PASSWORD)

            from Crypto.Cipher import AES

            cipher = AES.new(key, AES.MODE_CBC, iv)
            pt = cipher.decrypt(ct)

            pad = pt[-1]
            if 1 <= pad <= 16:
                pt = pt[:-pad]

            return pt.decode("utf-8", errors="replace")
        except Exception as e:
            print(f"Decryption error: {e}")
            return ""

    def _fetch_and_decrypt(self, url: str) -> dict:
        try:
            r = self.session.get(url, timeout=self.timeout)
            r.raise_for_status()
            encrypted = r.json().get("data", "")
            decrypted = self._decrypt_data(encrypted)
            if not decrypted:
                return {}

            parsed_json = json.loads(decrypted)

            with open("raw.txt", "a", encoding="utf-8") as f:
                f.write(f"\nURL: {url}\n")
                f.write("=" * 60 + "\n")
                f.write(json.dumps(parsed_json, indent=4))
                f.write("\n" + "=" * 60 + "\n")

            return parsed_json
        except Exception as e:
            print(f"Fetch/decrypt failed {url}: {e}")
            return {}

    def _get_api_url(self) -> Optional[str]:
        install_url = "https://firebaseinstallations.googleapis.com/v1/projects/sportzx-7cc3f/installations"
        install_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Dalvik/2.1.0 (Linux; Android 13)",
            "X-Android-Cert": "A0047CD121AE5F71048D41854702C52814E2AE2B",
            "X-Android-Package": "com.sportzx.live",
            "x-firebase-client": "H4sIAAAAAAAAAKtWykhNLCpJSk0sKVayio7VUSpLLSrOzM9TslIyUqoFAFyivEQfAAAA",
            "x-goog-api-key": "AIzaSyBa5qiq95T97xe4uSYlKo0Wosmye_UEf6w",
        }
        install_body = {
            "fid": "eOaLWBo8S7S1oN-vb23mkf",
            "appId": "1:446339309956:android:b26582b5d2ad841861bdd1",
            "authVersion": "FIS_v2",
            "sdkVersion": "a:18.0.0",
        }

        try:
            r = self.session.post(
                install_url,
                json=install_body,
                headers=install_headers,
                timeout=self.timeout,
            )
            r.raise_for_status()
            auth_token = r.json()["authToken"]["token"]
        except Exception as e:
            print(f"Firebase installation error: {e}")
            return None

        config_url = "https://firebaseremoteconfig.googleapis.com/v1/projects/446339309956/namespaces/firebase:fetch"
        config_headers = {
            "Content-Type": "application/json",
            "User-Agent": "Dalvik/2.1.0 (Linux; Android 13)",
            "X-Android-Cert": "A0047CD121AE5F71048D41854702C52814E2AE2B",
            "X-Android-Package": "com.sportzx.live",
            "X-Firebase-RC-Fetch-Type": "BASE/1",
            "X-Goog-Api-Key": "AIzaSyBa5qiq95T97xe4uSYlKo0Wosmye_UEf6w",
            "X-Goog-Firebase-Installations-Auth": auth_token,
        }

        config_body = {
            "appVersion": "2.1",
            "firstOpenTime": "2025-11-10T16:00:00.000Z",
            "timeZone": "Europe/Rome",
            "appInstanceIdToken": auth_token,
            "languageCode": "it-IT",
            "appBuild": "12",
            "appInstanceId": "eOaLWBo8S7S1oN-vb23mkf",
            "countryCode": "IT",
            "appId": "1:446339309956:android:b26582b5d2ad841861bdd1",
            "platformVersion": "33",
            "sdkVersion": "22.1.2",
            "packageName": "com.sportzx.live",
        }

        try:
            r = self.session.post(
                config_url,
                json=config_body,
                headers=config_headers,
                timeout=self.timeout,
            )
            r.raise_for_status()
            return r.json().get("entries", {}).get("api_url")
        except Exception as e:
            print(f"Remote Config error: {e}")
            return None

    def get_channels(self) -> List[SportzxChannel]:
        api_url = self._get_api_url()
        if not api_url:
            print("Failed to retrieve the API URL")
            return []

        channels_list: List[SportzxChannel] = []

        events_url = f"{api_url.rstrip('/')}/events.json"
        events = self._fetch_and_decrypt(events_url)

        if not isinstance(events, list):
            events = []

        valid_events = [
            e
            for e in events
            if isinstance(e, dict)
            and e.get("cat")
            and e["cat"].lower() not in self.excluded_categories
        ]

        for event in valid_events:
            eid = event.get("id")
            if not eid:
                continue

            ch_url = f"{api_url.rstrip('/')}/channels/{eid}.json"
            channels = self._fetch_and_decrypt(ch_url)

            if not isinstance(channels, list):
                continue

            event_info = event.get("eventInfo", {})
            team_a_flag = event_info.get("teamAFlag")
            team_b_flag = event_info.get("teamBFlag")

            raw_start = event_info.get("startTime", "")
            raw_end = event_info.get("endTime", "")

            start_time_gmt = raw_start.replace("/", "-") if raw_start else ""
            end_time_gmt = raw_end.replace("/", "-") if raw_end else ""

            formats_new = event.get("formatsNew", [])
            logo_map = {}
            if isinstance(formats_new, list):
                for fmt in formats_new:
                    if isinstance(fmt, dict) and fmt.get("title"):
                        logo_map[fmt["title"].strip().lower()] = fmt.get("logo")

            for ch in channels:
                if not isinstance(ch, dict):
                    continue

                link = ch.get("link", "")
                if not link:
                    continue

                components = link.split("|", 1)
                stream_url = components[0].strip()

                ch_title = ch.get("title", "")
                ch_logo = logo_map.get(ch_title.strip().lower()) if ch_title else None

                if not ch_logo and ch.get("logo"):
                    ch_logo = ch.get("logo")

                user_agent = None
                referer = ch.get("referer")
                origin = ch.get("origin")

                if len(components) > 1:
                    for param in components[1].split("&"):
                        if "=" in param:
                            k, v = param.split("=", 1)
                            kl = k.strip().lower()
                            v = v.strip()
                            if kl == "user-agent":
                                user_agent = v
                            elif kl == "referer":
                                referer = v
                            elif kl == "origin":
                                origin = v

                keyid = key = None
                api_val = ch.get("api")
                if api_val and ":" in api_val:
                    keyid, key = api_val.split(":", 1)

                channels_list.append(
                    SportzxChannel(
                        event_title=event.get("title", "Untitled Event"),
                        event_id=eid,
                        event_cat=event.get("cat", ""),
                        event_name=event_info.get("eventName", ""),
                        channel_title=ch_title,
                        stream_url=stream_url,
                        keyid=keyid,
                        key=key,
                        api=api_val,
                        referer=referer,
                        origin=origin,
                        headers=user_agent,
                        team_a_flag=team_a_flag,
                        team_b_flag=team_b_flag,
                        channel_logo=ch_logo,
                        start_time_gmt=start_time_gmt,
                        end_time_gmt=end_time_gmt,
                    )
                )

        return channels_list

    def _increase_time_by_one_hour(self, time_str: str) -> str:
        if not time_str or len(time_str) < 5 or ":" not in time_str:
            return time_str

        try:
            time_part = time_str.split()[-1][:5]
            hh, mm = map(int, time_part.split(":"))
            if not (0 <= hh <= 23 and 0 <= mm <= 59):
                return time_part

            new_time = datetime(2000, 1, 1, hh, mm) + timedelta(hours=1)
            return new_time.strftime("%H:%M")
        except:
            return time_str

    def generate_m3u(
        self,
        channels: List[SportzxChannel],
        filename: str = "Sportzx.m3u8",
        generic_logo: str = "https://via.placeholder.com/512/000000/FFFFFF?text=Sport",
    ) -> str:
        lines = ["#EXTM3U", "#EXT-X-VERSION:3", ""]

        included = 0

        for ch in channels:
            if not ch.stream_url or not ch.stream_url.lower().endswith(
                (".mpd", ".m3u8")
            ):
                continue

            included += 1

            event = (ch.event_title or "Event").strip()

            original_time = ""
            if ch.start_time_gmt and len(ch.start_time_gmt) >= 16:
                original_time = ch.start_time_gmt[11:16]

            shifted_time = self._increase_time_by_one_hour(original_time)
            time_part = f" {shifted_time}" if shifted_time else ""

            channel_suffix = ""
            if ch.channel_title and ch.channel_title.strip():
                channel_title = ch.channel_title.strip()
                if channel_title.lower() not in event.lower():
                    channel_suffix = f" ({channel_title})"

            final_name = f"{event}{time_part}{channel_suffix}".strip()
            clean_name = re.sub(r"[^\w\s\-\:\(\)\,\.\']", " ", final_name).strip()

            group = ch.event_cat.capitalize() if ch.event_cat else "Sportzx"
            logo = ch.channel_logo if ch.channel_logo else generic_logo

            tvg = re.sub(r"[^a-z0-9]", "", clean_name.lower())
            tvg_id = tvg[:50] if tvg else f"sportzx-{ch.event_id[:8]}"

            extinf = (
                f'#EXTINF:-1 tvg-id="{tvg_id}" '
                f'tvg-logo="{logo}" '
                f'group-title="{group}",{clean_name}'
            )

            lines.append(extinf)

            if ch.keyid and ch.key:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(
                    f"#KODIPROP:inputstream.adaptive.license_key={ch.keyid}:{ch.key}"
                )

            lines.append(ch.stream_url)
            lines.append("")

        content = "\n".join(lines).rstrip()

        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content + "\n")
            print(f"Playlist created: {filename}")
            print(f"Channels included: {included}")
        except Exception as e:
            print(f"Save error: {e}")

        return content


# --- REDUNDANT event_time PROPERTY REFACTOR ---
def generate_web_view_url(
    channels: list[SportzxChannel],
    include_without_keys: bool = False,
    generic_logo: str = "https://via.placeholder.com/512/000000/FFFFFF?text=Sport",
) -> list[dict]:
    grouped: dict[str, dict] = {}
    ungrouped = []

    for ch in channels:
        if not ch.stream_url:
            continue

        has_keys = bool(ch.keyid and ch.key)
        if not has_keys and not include_without_keys:
            continue

        stream_entry = {
            "web_view_url": ch.stream_url,
            "logo": ch.channel_logo if ch.channel_logo else generic_logo,
        }

        if has_keys:
            stream_entry["clearkey"] = f"{ch.keyid}:{ch.key}"

        if ch.channel_title and ch.channel_title.strip():
            stream_entry["channel_title"] = ch.channel_title.strip()

        event_name = (
            ch.event_name.strip() if ch.event_name and ch.event_name.strip() else None
        )
        if event_name:
            event_name = re.sub(r"[^\w\s\-\:\(\)\,\.\']", " ", event_name).strip()

        if event_name:
            if event_name not in grouped:
                grouped[event_name] = {
                    "event_name": event_name,
                    "team_a_flag": ch.team_a_flag if ch.team_a_flag else "",
                    "team_b_flag": ch.team_b_flag if ch.team_b_flag else "",
                    "start_time_gmt": ch.start_time_gmt,
                    "end_time_gmt": ch.end_time_gmt,
                    "streams": [],
                }
            grouped[event_name]["streams"].append(stream_entry)

        else:
            entry = {
                "team_a_flag": ch.team_a_flag if ch.team_a_flag else "",
                "team_b_flag": ch.team_b_flag if ch.team_b_flag else "",
                "start_time_gmt": ch.start_time_gmt,
                "end_time_gmt": ch.end_time_gmt,
                "streams": [stream_entry],
            }
            ungrouped.append(entry)

    return list(grouped.values()) + ungrouped


def generate_events_json(
    channels: list[SportzxChannel],
    generic_logo: str = "https://via.placeholder.com/512/000000/FFFFFF?text=Sport",
) -> list[dict]:
    events_list = []

    for ch in channels:
        if not ch.stream_url:
            continue

        event_name = (ch.event_title or "Event").strip()
        channel_title = (
            ch.channel_title.strip()
            if ch.channel_title and ch.channel_title.strip()
            else ""
        )
        if channel_title and channel_title.lower() not in event_name.lower():
            event_name += f" ({channel_title})"

        logo = ch.channel_logo if ch.channel_logo else generic_logo

        event_dict = {
            "name": event_name,
            "link": ch.stream_url,
            "logo": logo,
            "origin": ch.origin if ch.origin else "",
            "referrer": ch.referer if ch.referer else "",
            "userAgent": ch.headers
            if ch.headers
            else "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "cookie": "",
        }

        if ch.keyid and ch.key:
            event_dict["drmScheme"] = "clearkey"
            event_dict["drmLicense"] = f"{ch.keyid}:{ch.key}"

        events_list.append(event_dict)

    return events_list


if __name__ == "__main__":
    client = SportzxClient(timeout=15)

    print("Fetching channels...")
    channels = client.get_channels()

    generic_logo_url = "https://i.postimg.cc/xdhSY2xq/does-anyone-have-transparent-sportzx-icons-they-can-share-v0-wyufeqaxobff1.png"

    print("Generating web-view urls...")
    web_views = generate_web_view_url(channels, generic_logo=generic_logo_url)

    print(f"Saving {len(web_views)} web-views")

    with open("web-view-urls.json", "w") as fh:
        json.dump(web_views, fh, indent=4)

    print(f"Found {len(channels)} channels total")

    if channels:
        print("Generating Sportzx.m3u8 playlist...")
        client.generate_m3u(
            channels=channels,
            filename="file.txt",
            generic_logo=generic_logo_url,
        )

        print("Generating events.json...")
        events_data = generate_events_json(
            channels=channels, generic_logo=generic_logo_url
        )
        with open("events.json", "w", encoding="utf-8") as f:
            json.dump(events_data, f, indent=4)
        print(f"Saved {len(events_data)} events to events.json")
        print("\nSUCCESS: All data has been saved to files.")
    else:
        print("No channels found")
