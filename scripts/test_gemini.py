#!/usr/bin/env python3
"""
Test script for Google Gemini LLM integration.

Usage:
    GOOGLE_API_KEY=your-key python scripts/test_gemini.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set your API key here for testing (or use environment variable)
# API Key 1
API_KEY_1 = "AIzaSyDOoBXHRce3W7levjFjQppz4rZuoh-wH8U"
# API Key 2 (backup)
API_KEY_2 = "AIzaSyDko5VP_wMr7T7z9Z-76SEDGWW9BomWaSs"


async def test_gemini():
    """Test Google Gemini LLM."""
    from app.services.llm_service import GoogleLLM, LLMMessage, get_llm, LLMProvider
    
    print("=" * 70)
    print("GOOGLE GEMINI LLM TEST")
    print("=" * 70)
    
    # Try first API key
    api_key = os.getenv("GOOGLE_API_KEY") or API_KEY_1
    print(f"\n🔑 Using API Key: {api_key[:20]}...")
    
    # List available models first
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        print("\n📋 Available models:")
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"   - {m.name}")
    except Exception as e:
        print(f"   ⚠️ Could not list models: {e}")
    
    try:
        # Create Google LLM instance
        llm = GoogleLLM(api_key=api_key, model="gemini-2.0-flash")
        
        # Test 1: Simple generation
        print("\n📝 Test 1: Simple Generation")
        print("-" * 50)
        
        messages = [
            LLMMessage(role="system", content="You are a helpful insurance policy assistant."),
            LLMMessage(role="user", content="What is a deductible in insurance? Explain briefly."),
        ]
        
        response = await llm.generate(messages)
        
        print(f"✅ Response received!")
        print(f"   Model: {response.model}")
        print(f"   Usage: {response.usage}")
        print(f"\n📄 Content:")
        print("-" * 50)
        print(response.content)
        print("-" * 50)
        
        # Test 2: Streaming generation
        print("\n📝 Test 2: Streaming Generation")
        print("-" * 50)
        
        messages = [
            LLMMessage(role="user", content="List 3 types of car insurance coverage in bullet points."),
        ]
        
        print("🌊 Streaming response:")
        full_response = ""
        async for chunk in llm.generate_stream(messages):
            print(chunk, end="", flush=True)
            full_response += chunk
        
        print("\n" + "-" * 50)
        print(f"✅ Streamed {len(full_response)} characters")
        
        # Test 3: Multi-turn conversation
        print("\n📝 Test 3: Multi-turn Conversation")
        print("-" * 50)
        
        messages = [
            LLMMessage(role="user", content="What is comprehensive coverage?"),
            LLMMessage(role="assistant", content="Comprehensive coverage protects your vehicle from non-collision incidents like theft, vandalism, natural disasters, and falling objects."),
            LLMMessage(role="user", content="How is that different from collision coverage?"),
        ]
        
        response = await llm.generate(messages)
        print(f"📄 Response:\n{response.content}")
        
        # Test 4: Factory function
        print("\n📝 Test 4: Using Factory Function")
        print("-" * 50)
        
        # Set env variable for factory
        os.environ["GOOGLE_API_KEY"] = api_key
        llm_from_factory = get_llm(LLMProvider.GOOGLE)
        
        messages = [LLMMessage(role="user", content="Say 'Hello from Gemini!' in one sentence.")]
        response = await llm_from_factory.generate(messages)
        print(f"✅ Factory response: {response.content}")
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print(f"   Type: {type(e).__name__}")
        
        # Try backup key
        if api_key == API_KEY_1:
            print(f"\n🔄 Trying backup API key...")
            os.environ["GOOGLE_API_KEY"] = API_KEY_2
            return await test_gemini()
        
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_gemini())
    sys.exit(0 if success else 1)

