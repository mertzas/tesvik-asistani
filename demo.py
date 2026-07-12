#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tesvik Asistani - Demo (Otomatik Test)
"""
import requests
import json
import sys

API_URL = "http://localhost:8000"

def check_server():
    try:
        resp = requests.get(f"{API_URL}/health", timeout=3)
        return resp.status_code == 200
    except:
        return False

def search(question):
    try:
        resp = requests.post(
            f"{API_URL}/api/sor",
            json={"question": question},
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    return None

# Test sorguları
test_queries = [
    "KOSGEB",
    "TUBİTAK",
    "KGF",
    "İnovasyon",
    "Ar-Ge"
]

print("=" * 70)
print("TESVIK ASISTANI - OTOMATIK DEMO")
print(f"API: {API_URL}")
print("=" * 70)

print("\n1. SERVER KONTROLU...")
if not check_server():
    print("   HATA: Server calismiyor!")
    print("   Basla: python test_app.py")
    sys.exit(1)

print("   OK - Server calisıyor")

print("\n2. DEMO SORGULARI...")
print("-" * 70)

for i, question in enumerate(test_queries, 1):
    print(f"\n[{i}] Sorgu: '{question}'")
    print("-" * 70)

    result = search(question)
    if result and result.get("tesvikler"):
        print(f"    Bulunan: {result['count']} sonuc")
        for j, tesvik in enumerate(result["tesvikler"], 1):
            print(f"\n    {j}. [{tesvik['kurum']}] {tesvik['baslik']}")
            print(f"       {tesvik['ozet'][:80]}...")
            print(f"       Hedef: {tesvik['hedef_kitle']}")
    else:
        print(f"    Sonuc bulunamadi")

print("\n" + "=" * 70)
print("DEMO TAMAMLANDI")
print("=" * 70)
