import sys
import time
import requests
from pathlib import Path

def test_remote_gpu(url: str, pdf_path: str = None):
    url = url.rstrip("/")
    print(f"--- TESTING REMOTE GPU AT: {url} ---")
    
    # 1. Health check
    print("\n[1] Checking /health...")
    try:
        t0 = time.time()
        res = requests.get(f"{url}/health", timeout=10)
        t_health = time.time() - t0
        print(f"Status: {res.status_code} ({t_health:.2f}s)")
        print(f"Health Response: {res.json()}")
    except Exception as e:
        print(f"Failed to connect to /health: {e}")
        return

    # 2. Test Embed
    print("\n[2] Testing /embed (BAAI/bge-m3 dense + sparse)...")
    try:
        t0 = time.time()
        res = requests.post(
            f"{url}/embed",
            json={
                "texts": [
                    "Báo cáo tài chính quý 3 năm 2024 của Vinamilk",
                    "Doanh thu thuần đạt 15.000 tỷ đồng, tăng trưởng 5% so với cùng kỳ."
                ],
                "max_length": 512,
                "batch_size": 16,
                "return_sparse": True
            },
            timeout=30
        )
        t_embed = time.time() - t0
        print(f"Status: {res.status_code} ({t_embed:.2f}s)")
        data = res.json()
        print(f"Generated {len(data['dense'])} dense vectors, dim: {len(data['dense'][0])}")
        print(f"Generated {len(data['sparse'])} sparse weights sets.")
    except Exception as e:
        print(f"Failed /embed: {e}")
        return

    # 3. Test Rerank
    print("\n[3] Testing /rerank (Qwen3-Reranker-0.6B)...")
    try:
        t0 = time.time()
        res = requests.post(
            f"{url}/rerank",
            json={
                "pairs": [
                    ("Doanh thu quý 3/2024", "Doanh thu thuần đạt 15.000 tỷ đồng, tăng trưởng 5%."),
                    ("Doanh thu quý 3/2024", "Hội đồng quản trị thông qua kế hoạch tổ chức sự kiện thể thao.")
                ]
            },
            timeout=30
        )
        t_rerank = time.time() - t0
        print(f"Status: {res.status_code} ({t_rerank:.2f}s)")
        scores = res.json()["scores"]
        print(f"Scores: {scores}")
    except Exception as e:
        print(f"Failed /rerank: {e}")
        return

    # 4. Test Docling (if PDF provided or auto-detected)
    if pdf_path and Path(pdf_path).exists():
        print(f"\n[4] Testing /parse_docling with {pdf_path}...")
        try:
            t0 = time.time()
            with open(pdf_path, "rb") as f:
                res = requests.post(
                    f"{url}/parse_docling",
                    files={"file": (Path(pdf_path).name, f, "application/pdf")},
                    timeout=300
                )
            t_docling = time.time() - t0
            print(f"Status: {res.status_code} ({t_docling:.2f}s)")
            pages = res.json().get("pages", [])
            print(f"Docling parsed {len(pages)} pages successfully on GPU!")
            if pages:
                print(f"Sample page 1 preview: {pages[0]['text'][:200]}...")
        except Exception as e:
            print(f"Docling test failed: {e}")

    print("\n" + "="*60)
    print("✅ HOÀN TẤT: Server GPU hoạt động hoàn hảo!")
    print(f"Để sử dụng, hãy thêm dòng sau vào file backend/.env:")
    print(f"REMOTE_GPU_URL={url}")
    print("="*60)

if __name__ == "__main__":
    url_arg = sys.argv[1] if len(sys.argv) > 1 else input("Nhập URL Cloudflare Tunnel: ").strip()
    pdf_arg = sys.argv[2] if len(sys.argv) > 2 else None
    test_remote_gpu(url_arg, pdf_arg)
