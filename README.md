# Sample Project

This is a template to help you start a Synthetix project using the [Python SDK](https://github.com/Synthetixio/python-sdk).

## Getting Started

1. Before you begin, ensure you have:
* A RPC endpoint like [Infura](https://infura.io/) or [Alchemy](https://www.alchemy.com/)
* A wallet address **and** the private key for that address
* Installed Python 3.8 or greater
    * Run `python --version` in your terminal to check

2. Download this repository to a preferred location on your computer. Here's how:

```bash
git clone https://github.com/Synthetixio/project-template-python.git
cd project-template-python
```

3. Set up the required packages in a virtual environment:

```bash
python3 -m venv env
source env/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

4. Make a copy of the .env.example file, name it .env, and then enter the details for your RPC and wallet.

```
PROVIDER_RPC=<An RPC endpoint>
PRIVATE_KEY=<Your private key (optional)>
```

The private key is optional. If one is not provided, the SDK can simulate a specified address, but transaction signing will be disabled.

5. Run the status script:

```bash
python status.py
```

You should see results displaying your balances and market information, as shown below:

```bash
$ python status.py

Address: 0xD199157bB8a47bEF78e539908dEE5A41e7d5FE9f
ETH balance: 1.287
WETH balance: 0.0
sUSD balance: 10238.922

Perps accounts: 100, 101, 102
Perps default account: 100
Perps markets: BTC, ETH, LINK, OP, SNX
```

Congratulations! If you've made it this far you can start to build your own project using the Python SDK. More scripts are available in the `scripts` directory.

## Running Scripts

If you've completed the steps above, you can run any of the scripts in the `scripts` directory. For example:

```bash
python scripts/create_account.py
```

By default, these scripts won't submit transactions. To enable this, you must edit the script and set `submit=True`. This precaution helps avoid unintended transactions on the blockchain.
Always use caution and carefully review the code before submitting transactions.

## Documentation

For a full list of available methods, see the [Python SDK documentation](https://synthetixio.github.io/python-sdk/).