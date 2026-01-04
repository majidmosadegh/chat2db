#!/usr/bin/env python3

# Simple test for RTL logic
def test_rtl_logic():
    languages = ['fa', 'persian', 'en', 'english', None]

    for lang in languages:
        is_rtl = lang == 'fa' or lang == 'persian'
        print(f"Language: {lang or 'None'} -> RTL: {is_rtl}")

if __name__ == "__main__":
    test_rtl_logic()
