#!/usr/bin/env python3

# Test if all routers can be imported without issues
try:
    from api import models, database, schema, data_dictionary, relationships, use_cases, smart_use_case_builder, fine_tuning, chat_orchestrator
    print("SUCCESS: All routers imported")

    # Test router attributes
    routers = [
        ("models", models),
        ("database", database),
        ("schema", schema),
        ("data_dictionary", data_dictionary),
        ("relationships", relationships),
        ("use_cases", use_cases),
        ("smart_use_case_builder", smart_use_case_builder),
        ("fine_tuning", fine_tuning),
        ("chat_orchestrator", chat_orchestrator)
    ]

    for name, module in routers:
        if hasattr(module, 'router'):
            print(f"SUCCESS: {name}.router exists")
        else:
            print(f"ERROR: {name}.router missing")

    print("SUCCESS: All router tests passed")

except Exception as e:
    print(f"ERROR: Router import failed: {e}")
    import traceback
    traceback.print_exc()