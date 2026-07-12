#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tesvik Asistani - CLI Search Tool
"""
import requests
import json

API_URL = "http://localhost:8000"

def check_server():
    try:
        resp = requests.get(f"{API_URL}/health")
        return resp.status_code == 200
    except:
        return False

def search(question):
    try:
        resp = requests.post(
            f"{API_URL}/api/sor",
            json={"question": question},
            headers={"Content-Type": "application/json"}
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error: {e}")
    return None

print("=" * 60)
print("TESVIK ASISTANI - INTERACTIVE SEARCH")
print(f"API: {API_URL}")
print("=" * 60)

if not check_server():
    print("\nERROR: Server is not running!")
    print("Start server: python test_app.py")
    exit(1)

print("\nServer: OK")
print("Type 'quit' to exit\n")

while True:
    question = input("\nSearch: ").strip()

    if question.lower() == "quit":
        break

    if not question:
        continue

    result = search(question)
    if result:
        print(f"\nFound {result['count']} results for: {question}")
        print("-" * 60)

        for i, tesvik in enumerate(result["tesvikler"], 1):
            print(f"\n{i}. [{tesvik['kurum']}] {tesvik['baslik']}")
            print(f"   {tesvik['ozet'][:100]}...")
            print(f"   Target: {tesvik['hedef_kitle']}")
    else:
        print("No results found")

print("\nGoodbye!")
