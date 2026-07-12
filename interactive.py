#!/usr/bin/env python3
"""
Interactive Teşvik Asistanı CLI
Localhost API'ye bağlanıp sorgu yapıyor
"""
import requests
import json
from colorama import Fore, Back, Style

API_URL = "http://localhost:8000"

def print_header():
    print("\n" + "="*60)
    print(f"  🎯 Teşvik Asistanı - Interactive Search")
    print(f"  API: {API_URL}")
    print("="*60 + "\n")

def check_server():
    try:
        resp = requests.get(f"{API_URL}/health")
        if resp.status_code == 200:
            print(f"✅ Server Çalışıyor: {API_URL}")
            return True
    except:
        pass
    print(f"❌ Server Erişilemiyor: {API_URL}")
    return False

def search_tesvikler(question: str):
    try:
        print(f"\n🔍 Aranıyor: '{question}'...\n")

        resp = requests.post(
            f"{API_URL}/api/sor",
            json={"question": question},
            headers={"Content-Type": "application/json"}
        )

        if resp.status_code != 200:
            print(f"❌ API Hatası: {resp.status_code}")
            return

        data = resp.json()

        if data["count"] == 0:
            print(f"📭 '{question}' için sonuç bulunamadı\n")
            return

        print(f"✅ {data['count']} sonuç bulundu:\n")
        print("-" * 60)

        for i, tesvik in enumerate(data["tesvikler"], 1):
            print(f"\n{i}. [{tesvik['kurum'].upper()}] {tesvik['baslik']}")
            print(f"   📝 {tesvik['ozet'][:100]}...")
            print(f"   👥 Hedef: {tesvik['hedef_kitle']}")

        print("\n" + "-" * 60 + "\n")

    except Exception as e:
        print(f"❌ Hata: {e}\n")

def main():
    print_header()

    if not check_server():
        print("\n💡 Tip: Sunucuyu başlat: python test_app.py\n")
        return

    print("\n💡 İpucu: 'quit' yazarak çık\n")

    while True:
        try:
            question = input("🔍 Sorguyu girin (quit=çık): ").strip()

            if question.lower() == "quit":
                print("\n👋 Hoşça kalın!\n")
                break

            if not question:
                print("⚠️  Lütfen bir soru yazın\n")
                continue

            search_tesvikler(question)

        except KeyboardInterrupt:
            print("\n\n👋 Hoşça kalın!\n")
            break
        except Exception as e:
            print(f"❌ Hata: {e}\n")

if __name__ == "__main__":
    main()
