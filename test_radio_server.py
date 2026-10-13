import time

from radio_server.server import RadioStreamServer


SOURCE_URL = (
    "https://samplelib.com/mp3/sample-3s.mp3"
)


server = RadioStreamServer()

server.set_source(
    SOURCE_URL
)

server.start()

print()
print(
    "Test stream:"
)

print(
    "http://127.0.0.1:8765/stream.mp3"
)

print()

print(
    "Press CTRL+C to stop."
)

try:

    while True:
        time.sleep(1)

except KeyboardInterrupt:

    print()
    print(
        "Stopping server..."
    )

    server.stop()
