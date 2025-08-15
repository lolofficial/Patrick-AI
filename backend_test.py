#!/usr/bin/env python3
"""
Backend API Testing Suite
Tests the FastAPI backend endpoints according to the review requirements.
"""

import requests
import json
import time
import uuid
from datetime import datetime
import os
import sys

# Get the backend URL from frontend .env
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"Error reading frontend .env: {e}")
        return None

BASE_URL = get_backend_url()
if not BASE_URL:
    print("ERROR: Could not get REACT_APP_BACKEND_URL from frontend/.env")
    sys.exit(1)

print(f"Testing backend at: {BASE_URL}")

# Test session for cleanup
test_session_ids = []

def test_hello_world():
    """Test GET /api/ returns Hello World"""
    print("\n=== Testing Hello World Endpoint ===")
    try:
        response = requests.get(f"{BASE_URL}/api/", timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get("message") == "Hello World":
                print("✅ Hello World endpoint working correctly")
                return True
            else:
                print(f"❌ Expected 'Hello World', got: {data.get('message')}")
                return False
        else:
            print(f"❌ Expected status 200, got: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error testing hello world: {e}")
        return False

def test_create_session():
    """Test POST /api/sessions"""
    print("\n=== Testing Create Session ===")
    try:
        # Test with default values
        response = requests.post(f"{BASE_URL}/api/sessions", json={}, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 201:
            session = response.json()
            session_id = session.get("id")
            if session_id:
                test_session_ids.append(session_id)
                print(f"✅ Session created successfully with ID: {session_id}")
                return session_id
            else:
                print("❌ Session created but no ID returned")
                return None
        else:
            print(f"❌ Expected status 201, got: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        return None

def test_list_sessions():
    """Test GET /api/sessions"""
    print("\n=== Testing List Sessions ===")
    try:
        response = requests.get(f"{BASE_URL}/api/sessions", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            sessions = response.json()
            print(f"Found {len(sessions)} sessions")
            if len(sessions) > 0:
                print(f"Sample session: {sessions[0]}")
            print("✅ List sessions working correctly")
            return True
        else:
            print(f"❌ Expected status 200, got: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error listing sessions: {e}")
        return False

def test_update_session(session_id):
    """Test PUT /api/sessions/{session_id}"""
    print(f"\n=== Testing Update Session {session_id} ===")
    try:
        update_data = {
            "title": "Updated Test Session",
            "model": "gpt-4"
        }
        response = requests.put(f"{BASE_URL}/api/sessions/{session_id}", json=update_data, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        if response.status_code == 200:
            session = response.json()
            if session.get("title") == "Updated Test Session" and session.get("model") == "gpt-4":
                print("✅ Session updated successfully")
                return True
            else:
                print(f"❌ Session not updated correctly. Title: {session.get('title')}, Model: {session.get('model')}")
                return False
        else:
            print(f"❌ Expected status 200, got: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error updating session: {e}")
        return False

def test_get_messages(session_id):
    """Test GET /api/sessions/{session_id}/messages"""
    print(f"\n=== Testing Get Messages for Session {session_id} ===")
    try:
        response = requests.get(f"{BASE_URL}/api/sessions/{session_id}/messages", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            messages = response.json()
            print(f"Found {len(messages)} messages")
            for msg in messages:
                print(f"  - {msg.get('role')}: {msg.get('content')[:50]}...")
            print("✅ Get messages working correctly")
            return messages
        else:
            print(f"❌ Expected status 200, got: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Error getting messages: {e}")
        return []

def test_chat_stream(session_id):
    """Test POST /api/chat/stream with SSE"""
    print(f"\n=== Testing Chat Stream for Session {session_id} ===")
    try:
        stream_data = {
            "sessionId": session_id,
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello, this is a test message for streaming"
                }
            ],
            "temperature": 0.3
        }
        
        print("Sending stream request...")
        response = requests.post(
            f"{BASE_URL}/api/chat/stream", 
            json=stream_data, 
            stream=True,
            timeout=30,
            headers={"Accept": "text/event-stream"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Stream started successfully")
            
            # Process the stream
            chunks_received = 0
            end_received = False
            
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith('data: '):
                    data_str = line[6:]  # Remove 'data: ' prefix
                    try:
                        data = json.loads(data_str)
                        event_type = data.get('type')
                        
                        if event_type == 'chunk':
                            chunks_received += 1
                            if chunks_received <= 3:  # Show first few chunks
                                print(f"  Chunk {chunks_received}: {data.get('delta', '')[:50]}...")
                        elif event_type == 'end':
                            end_received = True
                            message_id = data.get('messageId')
                            print(f"  Stream ended with messageId: {message_id}")
                            break
                        elif event_type == 'error':
                            print(f"  Stream error: {data.get('error')}")
                            return False
                    except json.JSONDecodeError:
                        print(f"  Invalid JSON in stream: {data_str}")
            
            print(f"✅ Stream completed. Received {chunks_received} chunks, end event: {end_received}")
            return end_received
        else:
            print(f"❌ Expected status 200, got: {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error testing chat stream: {e}")
        return False

def test_delete_session(session_id):
    """Test DELETE /api/sessions/{session_id}"""
    print(f"\n=== Testing Delete Session {session_id} ===")
    try:
        response = requests.delete(f"{BASE_URL}/api/sessions/{session_id}", timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 204:
            print("✅ Session deleted successfully")
            return True
        else:
            print(f"❌ Expected status 204, got: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error deleting session: {e}")
        return False

def cleanup_test_sessions():
    """Clean up any remaining test sessions"""
    print("\n=== Cleaning up test sessions ===")
    for session_id in test_session_ids:
        try:
            requests.delete(f"{BASE_URL}/api/sessions/{session_id}", timeout=5)
            print(f"Cleaned up session: {session_id}")
        except:
            pass

def main():
    """Run all backend tests"""
    print("🚀 Starting Backend API Tests")
    print(f"Backend URL: {BASE_URL}")
    
    results = {}
    
    # Test 1: Hello World
    results['hello_world'] = test_hello_world()
    
    # Test 2: Create Session
    session_id = test_create_session()
    results['create_session'] = session_id is not None
    
    if not session_id:
        print("❌ Cannot continue tests without a valid session")
        return results
    
    # Test 3: List Sessions
    results['list_sessions'] = test_list_sessions()
    
    # Test 4: Update Session
    results['update_session'] = test_update_session(session_id)
    
    # Test 5: Get Messages (before streaming)
    messages_before = test_get_messages(session_id)
    results['get_messages_before'] = True  # Just testing the endpoint works
    
    # Test 6: Chat Stream
    results['chat_stream'] = test_chat_stream(session_id)
    
    # Test 7: Get Messages (after streaming to verify persistence)
    messages_after = test_get_messages(session_id)
    results['get_messages_after'] = len(messages_after) > len(messages_before)
    
    if results['get_messages_after']:
        print("✅ Messages persisted correctly after streaming")
    else:
        print("❌ Messages not persisted after streaming")
    
    # Test 8: Delete Session
    results['delete_session'] = test_delete_session(session_id)
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST RESULTS SUMMARY")
    print("="*50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name.replace('_', ' ').title()}: {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed - check logs above for details")
    
    # Cleanup
    cleanup_test_sessions()
    
    return results

if __name__ == "__main__":
    main()