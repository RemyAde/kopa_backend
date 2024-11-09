import asyncio
import websockets
import json

async def test_websocket():
    url = "ws://localhost:8000/ws/672d645ca4ceca3baaf78b44"
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImdyYXZpdGVlZTQzM0Bnb3RnZWwub3JnIiwiaWQiOiI2NzA5ZWI5YzY3NWNjMmNlMDQ1MDk2MjgiLCJleHAiOjE3MzEwMzM5MzV9.He_ikxkeb1JEZJQIHrH5ospEREcjkvx3JqwiPOJE0iI"

    headers = [("Authorization", f"Bearer {token}")]

    async with websockets.connect(url, extra_headers=headers) as websocket:
        message = {
            "content": "Hello, this is a test message!"
        }
        await websocket.send(json.dumps(message))

        try:
            while True:
                response = await websocket.recv()
                print("Received:", response)
        except websockets.exceptions.ConnectionClosed as e:
            print(f"Connection closed: {e}")

asyncio.run(test_websocket())