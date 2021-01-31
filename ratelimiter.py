"""Rate Limiter class to keep track of our calls to the twitter api."""

import time

class RateLimiter():
    def __init__(self, rate, per):
        self.rate = rate
        self.per = per + time.time() # Unit: seconds
        self.start_count = 0
        self.start_time = time.time()
    
    def message_sent(self):
        # If our alloted period resets
        if (time.time() - self.start_time) > self.per:
            self.start_time = time.time()
            self.start_count = 0
        self.start_count += 1
        # Our program has exceeded the alloted rate limit
        if self.start_count >= self.rate:
            time.sleep(self.per - time.time())
