class MusicQueue:

    def __init__(self):

        self.queue = []

        self.current_song = None

        self.is_paused = False

    # ==========================
    # Add Song
    # ==========================

    def add(
        self,
        song
    ):

        self.queue.append(
            song
        )

    # ==========================
    # Get Next Song
    # ==========================

    def next_song(self):

        if self.queue:

            self.current_song = (
                self.queue.pop(0)
            )

            self.is_paused = False

            return self.current_song

        self.current_song = None

        self.is_paused = False

        return None

    # ==========================
    # Skip
    # ==========================

    def skip(self):

        return self.next_song()

    # ==========================
    # Pause
    # ==========================

    def pause(self):

        if self.current_song:

            self.is_paused = True

            return True

        return False

    # ==========================
    # Resume
    # ==========================

    def resume(self):

        if self.current_song:

            self.is_paused = False

            return True

        return False

    # ==========================
    # Stop
    # ==========================

    def stop(self):

        self.current_song = None

        self.is_paused = False

    # ==========================
    # Clear Queue
    # ==========================

    def clear(self):

        self.queue.clear()

    # ==========================
    # Remove Song
    # ==========================

    def remove(
        self,
        index
    ):

        if 0 <= index < len(
            self.queue
        ):

            return self.queue.pop(
                index
            )

        return None

    # ==========================
    # Get Queue
    # ==========================

    def get_queue(self):

        return self.queue.copy()

    # ==========================
    # Get Current Song
    # ==========================

    def get_current_song(self):

        return self.current_song