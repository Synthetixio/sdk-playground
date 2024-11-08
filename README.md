# SDK Playground

This repository contains a suite of tests, scripts, and notebook templates to get started using the Synthetix [Python SDK](https://github.com/Synthetixio/python-sdk) and interacting with the protocol. Visit [tests](tests/README.md) for more information on testing contracts and creating test environments.

## Installation

1. Before you begin, ensure you have:

- An API key from [Alchemy](https://www.alchemy.com/)
- A wallet address **and** the private key for that address (optional)
- Installed Python 3.10 or greater
  - Run `python --version` in your terminal to check

2. Clone this repository:

```bash
git clone https://github.com/Synthetixio/sdk-playground.git
cd sdk-playground
```

3. Install dependencies using [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

4. Install [Foundry](https://github.com/foundry-rs/foundry):

Review the [installation guide](https://book.getfoundry.sh/getting-started/installation) or run the following:

```bash
curl -L https://foundry.paradigm.xyz | bash

# install foundry
foundryup
```

5. Install `ape` plugins:

```bash
uv run ape plugins install .
```

6. Make a copy of the `.env.example` file, name it .env, and then enter the details for your RPC and wallet.

The private key is optional. If one is not provided, the SDK will simulate the specified address, but transaction signing will be disabled.

## Running Scripts

If you've completed the steps above, you can run any of the scripts in the `scripts` directory using the Ape framework. For example:

```bash
# run the file at scripts/base_fork.py
uv run ape run base_fork
```

By default, these scripts won't submit transactions. To enable this, you must edit the script and set `submit=True`. This precaution helps avoid unintended transactions on the blockchain.
Always use caution and carefully review the code before submitting transactions.

## Notebooks

There are also some Jupyter notebooks that don't rely on the Ape framework. You can open these using VS Code or Jupyter Notebook. Use the environment created above to run these notebooks.

For example, if you've properly set up your notebook environment, you can copy the template from `notebooks/templates/base_sepolia.ipynb` and start calling the contracts. If a private key is provided, you can also submit transactions.

## Documentation

For a full list of available methods, see the [Python SDK documentation](https://synthetixio.github.io/python-sdk/).
