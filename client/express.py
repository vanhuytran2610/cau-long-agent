"""
Thin client over the existing Express backend.
FastAPI never touches MongoDB directly — every call goes through Express
routes carrying the admin's access token, so all business logic stays in one place.

Auto-refreshes the access token once if Express returns TOKEN_EXPIRED.
Callers can inspect `client.new_tokens` after a request to get the rotated pair.
"""

import os
from typing import Optional
import httpx

EXPRESS_BASE_URL = os.environ.get("EXPRESS_BASE_URL", "http://localhost:3000")
TIMEOUT = httpx.Timeout(60.0)  # calculate route calls Grok, can be slow


def _unwrap(resp: httpx.Response):
    """sendResponse shape: {statusCode, message, data}. Return a normalised dict."""
    try:
        body = resp.json()
    except Exception:
        return {"_status": resp.status_code, "_raw": resp.text}
    if isinstance(body, dict) and "data" in body:
        return {"_status": resp.status_code, "message": body.get("message"), "data": body["data"]}
    return {"_status": resp.status_code, "body": body}


class ExpressClient:
    def __init__(self, access_token: str, refresh_token: Optional[str] = None):
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._headers = {"Authorization": f"Bearer {access_token}"}
        # Set after a successful token rotation — main.py reads this and
        # returns the new pair to the frontend so it can update its store.
        self.new_tokens: Optional[dict] = None

    async def _try_refresh(self) -> bool:
        """Call /api/admin/refresh. Returns True and updates headers on success."""
        if not self._refresh_token:
            return False
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                resp = await client.post(
                    f"{EXPRESS_BASE_URL}/api/admin/refresh",
                    json={"refreshToken": self._refresh_token},
                )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                self._access_token = data["accessToken"]
                self._refresh_token = data["refreshToken"]
                self._headers = {"Authorization": f"Bearer {self._access_token}"}
                self.new_tokens = {
                    "accessToken": self._access_token,
                    "refreshToken": self._refresh_token,
                }
                return True
        except Exception:
            pass
        return False

    async def _req(self, method: str, path: str, **kw):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.request(
                method, f"{EXPRESS_BASE_URL}{path}", headers=self._headers, **kw
            )

        # Auto-retry once if access token expired
        if resp.status_code == 401:
            try:
                if resp.json().get("code") == "TOKEN_EXPIRED" and await self._try_refresh():
                    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                        resp = await client.request(
                            method, f"{EXPRESS_BASE_URL}{path}", headers=self._headers, **kw
                        )
            except Exception:
                pass

        return _unwrap(resp)

    # --- READ ---
    async def list_categories(self):
        return await self._req("GET", "/api/categories")

    async def list_participants(self, category_id: str):
        return await self._req("GET", f"/api/participants/{category_id}")

    # --- WRITE ---
    async def create_category(self, name: str, content: str = "", is_selected: bool = False):
        return await self._req("POST", "/api/categories", json={"name": name, "content": content, "is_selected": is_selected})

    async def edit_category(self, category_id: str, name: str, content: str, is_selected: bool):
        return await self._req(
            "PUT", f"/api/categories/{category_id}",
            json={"name": name, "content": content, "is_selected": is_selected},
        )

    async def delete_category(self, category_id: str):
        return await self._req("DELETE", f"/api/categories/{category_id}")

    async def calculate(self, category_id: str, payment_info: str):
        return await self._req(
            "POST", f"/api/categories/{category_id}/calculate",
            json={"paymentInfo": payment_info},
        )

    async def export_result(self, category_id: str, qr_img_url: Optional[str] = None,
                            qr_img_id: Optional[str] = None, qr_img_name: Optional[str] = None):
        payload = {}
        if qr_img_id:
            payload["qr_img_id"] = qr_img_id
        if qr_img_url:
            payload["qr_img_url"] = qr_img_url
        if qr_img_name:
            payload["qr_img_name"] = qr_img_name
        return await self._req("PUT", f"/api/categories/{category_id}/export", json=payload)

    async def add_participant(self, category_id: str, name: str, level: str, gender: str):
        return await self._req(
            "POST", f"/api/participants/{category_id}",
            json={"name": name, "level": level, "gender": gender},
        )

    async def delete_participant(self, category_id: str, participant_id: str):
        return await self._req(
            "DELETE", f"/api/participants/{category_id}/{participant_id}"
        )
