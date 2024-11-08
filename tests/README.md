# Synthetix SDK Tests

This directory contains test suites for various deployments of the Synthetix protocol using the [Synthetix Python SDK](https://github.com/Synthetixio/python-sdk). The tests cover the functionality of each of those deployments, testing "happy path" scenarios for users interacting with the protocol.

The tests use [ape](https://github.com/ApeWorX/ape) and [foundry](https://github.com/foundry-rs/foundry) to create forked environments for testing. Ensure you have followed the [installation instructions](../README.md) to set up the necessary dependencies.

## Test Structure

The tests are organized into subdirectories based on the network, cannon preset, and whether the deployment is a fork or not. For example:

```
- tests/
  - arbitrum-mainnet-fork/       # Arbitrum mainnet, main deployment, forked
  - arbitrum-sepolia-octo/       # Arbitrum sepolia, "octo" deployment, not forked
  - arbitrum-sepolia-octo-fork/  # Arbitrum sepolia, "octo" deployment, forked
  - ...
```

Each subdirectory contains test files for different components of the Synthetix protocol:

- `conftest.py`: Configuration and fixtures for the test suite
- `test_*_synthetix.py`: Tests for general functionality
- `test_*_core.py`: Tests for core LP functionality
- `test_*_spot.py`: Tests for spot markets
- `test_*_perps.py`: Tests for perps

## Running Tests

To run the tests, use the `ape` command from the root directory of the project. You can run all tests or specify a particular test file or directory. It is recommended to run one test suite at a time to avoid conflicts between anvil forks and avoid rate limiting.

```bash
# Run tests on a fork
uv run ape test tests/arbitrum-mainnet-fork/ --network arbitrum:mainnet-fork:foundry

# Run tests on a live network
uv run ape test tests/arbitrum-sepolia-octo/ --network arbitrum:sepolia:alchemy

# Run a specific test file
uv run ape test tests/arbitrum-sepolia-octo-fork/test_arbitrum_sepolia_octo_perps.py --network arbitrum:sepolia-fork:foundry
```

Tests that run on forked networks should seed an RPC signer account with the necessary tokens and balances to run the tests. When running on live networks, ensure that you're providing an address and private key in the `.env` file. Ensure that the account has the necessary tokens and balances to run the tests.

## Configuration

Test configuration is managed through `conftest.py` files in each test subdirectory. These files set up fixtures and other test-specific configurations.

## Adding New Tests

New tests can usually be copied from networks with similar deployments. When adding new tests, please follow these guidelines:

1. Review the `conftest.py` file, and adjust the `snx` fixture to set up the account with token balances and other necessary configurations.
2. Add `test_*_*.py` files for the new tests, following the existing structure.
3. Run the tests locally to ensure they pass before submitting a pull request.
