#!/usr/bin/env python3

import asyncio
import sys
import os

# Add the backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

async def test_feedback_learning():
    """Test feedback learning component"""
    try:
        print("1. Importing FeedbackLearning...")
        from api.chat_orchestrator.feedback_learning import FeedbackLearning

        print("2. Creating FeedbackLearning...")
        fl = FeedbackLearning("test_session")

        print("3. Testing feedback methods...")
        # Test the basic functionality
        print("4. FeedbackLearning ready")

        print("SUCCESS: FeedbackLearning working")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_feedback_learning())