# constants
PRECOMPILE_ADDRESS = "0x000000000000000000000000000000000000006C"
PRECOMPILE_BYTECODE = "0x608060405234801561001057600080fd5b506004361061014d5760003560e01c80636ecca45a116100c3578063ad26ce901161007c578063ad26ce90146102a8578063ba9c916e146102b1578063c6f7de0e146102a8578063eff01306146102df578063f5d6ded7146102e7578063f918379a146102f257600080fd5b80636ecca45a1461023a5780637a1ea7321461024b5780637a7d6beb146102685780638a5b1d2814610270578063963d6002146102785780639e6d7e311461028657600080fd5b806329eb31ee1161011557806329eb31ee146101c35780633dfb45b9146101ae57806341b247a8146101cc578063520acdd7146102125780635b39d23c14610220578063612af1781461022e57600080fd5b806302199f3414610152578063055f362f1461017c5780631d5b5c201461019157806325754f91146101ae5780632987d027146101b6575b600080fd5b6103e86107d0610bb85b604080519384526020840192909252908201526060015b60405180910390f35b6406fc23ac005b604051908152602001610173565b6113885b60405167ffffffffffffffff9091168152602001610173565b612710610195565b66b1a2bc2ec50000610183565b620f4240610195565b640e44118940631a161170642e90edd000629896806000815b604080519687526020870195909552938501929092526060840152608083015260a082015260c001610173565b67016345785d8a0000610183565b670de0b6b3a7640000610183565b606460c861012c61015c565b604051620186a08152602001610173565b61015c6102593660046102fc565b506105dc906109c490610dac90565b6103e8610195565b6101f4610195565b6706f05b59d3b20000610183565b6040517312345678901234567890123456789012345678908152602001610173565b620f4240610183565b6101e56102bf3660046102fc565b640e44118940631a161170642e90edd00062989680600081939550919395565b61c350610195565b6404a817c800610183565b633b9aca00610183565b60006020828403121561030e57600080fd5b81356001600160a01b038116811461032557600080fd5b939250505056fea26469706673582212202ffbee6debcc76fbb9ef82a3695a5374fc86e86588546876e23b0e3f74625e7864736f6c63430008130033"

def mock_arb_precompiles(snx):
    # get the provider
    provider = snx.web3.provider
    # set the bytecode
    provider.make_request(
        "anvil_setCode", [PRECOMPILE_ADDRESS, PRECOMPILE_BYTECODE]
    )
    snx.logger.info(f"Mocked Arbitrum gas oracle precompile at {PRECOMPILE_ADDRESS}")
