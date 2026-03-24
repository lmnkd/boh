// importiamo la libreria Web3
const Web3 = require('web3');

// URL della tua blockchain locale o remota
// Esempio per Ganache locale: http://127.0.0.1:7545
const blockchainURL = 'http://127.0.0.1:22000'; 

// Creiamo un'istanza di Web3
const web3 = new Web3(new Web3.providers.HttpProvider(blockchainURL));

// Verifichiamo la connessione
web3.eth.net.isListening()
    .then(() => console.log('Connesso alla blockchain!'))
    .catch(e => console.log('Errore di connessione:', e));

// Mostriamo il primo account disponibile
web3.eth.getAccounts()
    .then(accounts => console.log('Accounts disponibili:', accounts))
    .catch(e => console.log(e));