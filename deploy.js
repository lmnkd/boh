const Web3 = require('web3');

// Connessione al nodo Quorum
const web3 = new Web3('http://127.0.0.1:22000'); // porta node1

// ABI del contratto Storage
const abi = [
  {
    "inputs": [],
    "name": "retrieve",
    "outputs": [
      { "internalType": "uint256", "name": "", "type": "uint256" }
    ],
    "stateMutability": "view",
    "type": "function"
  },
  {
    "inputs": [
      { "internalType": "uint256", "name": "num", "type": "uint256" }
    ],
    "name": "store",
    "outputs": [],
    "stateMutability": "nonpayable",
    "type": "function"
  }
];

// Bytecode compilato con Solidity 0.6.12
const bytecode = '608060405234801561001057600080fd5b5060c78061001f6000396000f3fe6080604052348015600f57600080fd5b506004361060325760003560e01c80632e64cec11460375780636057361d146053575b600080fd5b603d607e565b6040518082815260200191505060405180910390f35b607c60048036036020811015606757600080fd5b81019080803590602001909291905050506087565b005b60008054905090565b806000819055505056fea2646970667358221220e84065ea0cbd9a23ed6ab5ee4361375c8507635165356c3eced78ed30156c10f64736f6c634300060c0033'; // metti il bytecode completo

(async () => {
  try {
    const accounts = await web3.eth.getAccounts();
    console.log('Deployer account:', accounts[0]);

    const contract = new web3.eth.Contract(abi);

    // Deploy
    const deployed = await contract.deploy({ data: bytecode }).send({
      from: accounts[0],
      gas: 3000000,
      privateFor: [] // deploy pubblico
    });

    console.log('Contratto deployato all\'indirizzo:', deployed.options.address);

    // ✅ Usa i nomi corretti delle funzioni
    await deployed.methods.store(42).send({ from: accounts[0] });
    const value = await deployed.methods.retrieve().call();
    console.log('Valore memorizzato nel contratto:', value);

  } catch (err) {
    console.error('Errore:', err);
  }
})();