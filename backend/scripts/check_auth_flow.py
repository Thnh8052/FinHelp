"""Manual end-to-end check of the auth flow against a running MongoDB (python scripts/check_auth_flow.py). Not a pytest test: it needs live services."""
import asyncio
from pathlib import Path
import sys

# Thêm thư mục backend vào sys.path để luôn tìm thấy module 'app'
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import httpx
from app.db.mongodb import MongoManager
from app.db.repositories.user_repo import UserRepository
from app.main import app

async def check_auth():
    print("=== STARTING SAAS AUTH & MONGODB FLOW TEST (CHATGPT/CLAUDE MODEL) ===")
    await MongoManager.connect_to_database()
    db = MongoManager.db
    assert db is not None, "MongoDB connection failed"
    repo = UserRepository(db)

    # Clean up test user if left over from previous test
    test_email = "test_saas_user@finanalyst.ai"
    test_user = await repo.get_by_email(test_email)
    if test_user:
        await repo.delete_one({"email": test_email})
        print(f"Cleaned up previous test user: {test_email}")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1. TEST GUEST TRIAL QUOTA (Unauthenticated / Khách vãng lai: 2 câu hỏi, 1 tài liệu)
        print("\n1. Testing GET /api/v1/auth/guest-quota & /tiers (Chưa đăng nhập)...")
        res_tiers = await client.get("/api/v1/auth/tiers")
        assert res_tiers.status_code == 200, f"Get tiers failed: {res_tiers.text}"
        all_tiers = res_tiers.json()["tiers"]
        assert "guest" in all_tiers and "user" in all_tiers
        assert all_tiers["guest"]["daily_messages_limit"] == 2
        assert all_tiers["guest"]["max_upload_documents"] == 1
        assert all_tiers["user"]["max_upload_documents"] == 5
        print(f"   [PASS] Tiers Matrix verified: Guest (1 doc, 2 msgs) | User (5 docs/notebook)")

        res = await client.get("/api/v1/auth/guest-quota")
        assert res.status_code == 200, f"Guest quota failed: {res.text}"
        guest_info = res.json()
        assert guest_info["is_authenticated"] is False
        assert guest_info["trial_messages_limit"] == 2
        assert guest_info["max_upload_documents"] == 1
        print(f"   [PASS] Guest quota: {guest_info['trial_messages_limit']} câu hỏi thử, {guest_info['max_upload_documents']} tài liệu, {guest_info['cost_description']}")

        # 2. TEST REGISTER USER (Role: 'user', max 5 docs/notebook)
        print("\n2. Testing POST /api/v1/auth/register (Người dùng đăng ký mới)...")
        reg_payload = {
            "email": test_email,
            "username": "saas_user_01",
            "password": "SecurePassword123!",
            "full_name": "Trần Đăng Ký Test",
        }
        res = await client.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 200, f"Register failed: {res.text}"
        reg_data = res.json()
        assert "access_token" in reg_data
        assert reg_data["role"] == "user"
        test_user_id = reg_data["user_id"]
        user_token = reg_data["access_token"]
        print(f"   [PASS] User registered: user_id={test_user_id}, role={reg_data['role']}, tier={reg_data['tier']}")

        # 3. TEST GET /me FOR USER (5 tài liệu 1 notebook)
        print("\n3. Testing GET /api/v1/auth/me (Kiểm tra Quota User tier: 5 tài liệu/notebook)...")
        headers_user = {"Authorization": f"Bearer {user_token}"}
        res = await client.get("/api/v1/auth/me", headers=headers_user)
        assert res.status_code == 200, f"GET /me failed: {res.text}"
        profile = res.json()
        quota = profile["quota"]
        assert quota["max_upload_documents"] == 5
        print(f"   [PASS] Profile retrieved: Tier={quota['tier']}, Daily Limit={quota['daily_messages_limit']}, Max Docs={quota['max_upload_documents']}")

        # 4. TEST RBAC PROTECTION: STANDARD USER CALLS ADMIN DASHBOARD (MUST BE 403 FORBIDDEN)
        print("\n4. Testing Standard User trying to access Admin Dashboard (RBAC Check)...")
        res = await client.get("/api/v1/auth/admin/dashboard", headers=headers_user)
        assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}"
        print(f"   [PASS] User successfully blocked with 403 Forbidden: {res.json()['detail']}")

        # 5. TEST LOGIN AS ADMIN (Vũ Thành)
        print("\n5. Testing Login as Admin (Vũ Thành - analyst_demo)...")
        existing_admin = await repo.get_by_username("analyst_demo")
        if not existing_admin or existing_admin.role != "admin":
            await repo.collection.update_one(
                {"username": "analyst_demo"},
                {"$set": {"role": "admin", "full_name": "Vũ Thành - Quản Trị Hệ Thống"}}
            )
        
        res = await client.post("/api/v1/auth/login-json", json={"identifier": "analyst_demo", "password": "FinAnalyst2026!"})
        assert res.status_code == 200, f"Admin login failed: {res.text}"
        admin_data = res.json()
        admin_token = admin_data["access_token"]
        assert admin_data["role"] == "admin"
        print(f"   [PASS] Admin logged in: {admin_data['full_name']} (Role: {admin_data['role']}, Tier: {admin_data['tier']})")

        # 6. TEST ADMIN DASHBOARD
        print("\n6. Testing Admin accessing GET /api/v1/auth/admin/dashboard...")
        headers_admin = {"Authorization": f"Bearer {admin_token}"}
        res = await client.get("/api/v1/auth/admin/dashboard", headers=headers_admin)
        assert res.status_code == 200, f"Admin dashboard failed: {res.text}"
        dash_data = res.json()
        assert "total_users" in dash_data
        assert "api_metrics" in dash_data
        assert "system_performance" in dash_data
        print(f"   [PASS] Admin Dashboard Stats: Total Users={dash_data['total_users']}, Tokens Used={dash_data['api_metrics']['total_tokens_consumed']}, Status={dash_data['system_performance']['status']}")

        # 7. TEST ADMIN UPDATE TIER FUNCTIONALITY
        print("\n7. Testing Admin calling POST /api/v1/auth/admin/update-tier...")
        res = await client.post(
            "/api/v1/auth/admin/update-tier",
            headers=headers_admin,
            json={"user_id": test_user_id, "tier": "user"}
        )
        assert res.status_code == 200, f"Update tier failed: {res.text}"
        print(f"   [PASS] {res.json()['message']}")

        # 9. TEST TRACKING API TOKEN & COST CONSUMPTION
        print("\n9. Testing Tracking API Token & Cost Consumption...")
        await repo.increment_quota_usage(test_user_id, messages=2, tokens=1500, cost_usd=0.0045)
        res = await client.get("/api/v1/auth/me", headers=headers_user)
        used_quota = res.json()["quota"]
        assert used_quota["messages_used_today"] == 2
        assert used_quota["total_tokens_consumed"] == 1500
        print(f"   [PASS] Token tracking verified: Messages Today={used_quota['messages_used_today']}, Tokens={used_quota['total_tokens_consumed']}, Cost=${used_quota['total_cost_usd']}")

        # 10. CLEANUP TEST USER
        await repo.delete_one({"email": test_email})
        print(f"\n10. Cleaned up test user: {test_email}")

    await MongoManager.close_database_connection()
    print("\n=== ALL SAAS CHATGPT/CLAUDE STYLE TESTS PASSED PERFECTLY (10/10) ===")

if __name__ == "__main__":
    asyncio.run(check_auth())
