# SDK Playground

This is a sample repository with some ideas using the [Python SDK](https://github.com/Synthetixio/python-sdk).

## Getting Started

1. Before you begin, ensure you have:
* An API key from [Alchemy](https://www.alchemy.com/)
* A wallet address **and** the private key for that address
* Installed Python 3.8 or greater
    * Run `python --version` in your terminal to check

2. Download this repository to a preferred location on your computer. Here's how:

```bash
git clone https://github.com/Synthetixio/sdk-playground.git
cd project-template-python
```

3. Set up the required packages in a virtual environment:

```bash
python3 -m venv env
source env/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
```

4. Install `ape` plugins:
    
```bash
ape plugins install .
```

5. Make a copy of the .env.example file, name it .env, and then enter the details for your RPC and wallet.


The private key is optional. If one is not provided, the SDK will simulate the specified address, but transaction signing will be disabled.


## Running Scripts

If you've completed the steps above, you can run any of the scripts in the `scripts` directory using the Ape framework. For example:

```bash
# run the file at scripts/base_fork.py
ape run base_fork
```

By default, these scripts won't submit transactions. To enable this, you must edit the script and set `submit=True`. This precaution helps avoid unintended transactions on the blockchain.
Always use caution and carefully review the code before submitting transactions.

## Notebooks

There are also some Jupyter notebooks that don't rely on the Ape framework. You can open these using VS Code or Jupyter Notebook. Use the environment created above to run these notebooks.

For example, if you've properly set up your notebook environment, you can copy the template from `notebooks/templates/base_sepolia.ipynb` and start calling the contracts. If a private key is provided, you can also submit transactions.

## Documentation

For a full list of available methods, see the [Python SDK documentation](https://synthetixio.github.io/python-sdk/).