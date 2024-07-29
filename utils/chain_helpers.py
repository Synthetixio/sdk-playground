import time

def mine_block(snx, chain, seconds=3):
    time.sleep(seconds)
    timestamp = int(time.time())

    chain.mine(1, timestamp=timestamp)
    snx.logger.info(f"Block mined at timestamp {timestamp}")
