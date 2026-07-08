"""
Thin client over the existing Express backend.
FastAPI never touches MongoDB directly — every call goes through Express
routes carrying the admin's JWT, so all business logic (calculateWithGroq,
name normalization, duplicate checks) stays in one place.
"""

import os
from typing import Optional
import httpx

EXPRESS_BASE_URL = os.environ.get("EXPRESS_BASE_URL", "http://localhost:3000")
TIMEOUT = httpx.Timeout(60.0)  # calculate route calls Grok, can be slow


def _unwrap(resp: httpx.Response):
    """sendResponse(res, status, message, data) -> {message, data} (shape may vary).
    Return data if present, else the whole JSON body."""
    try:
        body = resp.json()
    except Exception:
        return {"_status": resp.status_code, "_raw": resp.text}
    if isinstance(body, dict) and "data" in body:
        return {"_status": resp.status_code, "message": body.get("message"), "data": body["data"]}
    return {"_status": resp.status_code, "body": body}


class ExpressClient:
    def __init__(self, jwt: str):
        # The admin's token is attached to every outgoing request, so Express
        # authenticates the agent exactly as it would that admin.
        self._headers = {"Authorization": f"Bearer {jwt}"}

    async def _req(self, method: str, path: str, **kw):
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.request(
                method, f"{EXPRESS_BASE_URL}{path}", headers=self._headers, **kw
            )
        return _unwrap(resp)

    # --- READ ---
    # 1. list category:
    async def list_categories(self):
        return await self._req("GET", "/api/categories")

    # 2. list participants in a category:
    async def list_participants(self, category_id: str):
        return await self._req("GET", f"/api/participants/{category_id}")

    # --- WRITE ---
    # 3. create a new category:
    async def create_category(self, name: str, content: str = "", is_selected: bool = False):
        return await self._req("POST", "/api/categories", json={"name": name, "content": content, "is_selected": is_selected})

    # 4. update a category:
    async def edit_category(self, category_id: str, name: str, content: str, is_selected: bool):
        return await self._req(
            "PUT", f"/api/categories/{category_id}",
            json={"name": name, "content": content, "is_selected": is_selected},
        )
    
    # 5. delete a category:
    async def delete_category(self, category_id: str):
        return await self._req("DELETE", f"/api/categories/{category_id}")

    # 6. calculate expense for a category:
    async def calculate(self, category_id: str, payment_info: str):
        return await self._req(
            "POST", f"/api/categories/{category_id}/calculate",
            json={"paymentInfo": payment_info},
        )

    # 7. export result of 1 category (set isShowMoney=true) and attach a QR image:
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

    # 8. add participant to category:
    async def add_participant(self, category_id: str, name: str, level: str, gender: str):
        return await self._req(
            "POST", f"/api/participants/{category_id}",
            json={"name": name, "level": level, "gender": gender},
        )
    
    # 9. delete participant from category:
    async def delete_participant(self, category_id: str, participant_id: str):
        return await self._req(
            "DELETE", f"/api/participants/{category_id}/{participant_id}"
        )
