// allow the script to access the file system on disk
const fs = require('fs');
const os = require('os');
const maxFiles = 20;

// create the a directory for block headers and transactions if they doesn't exist already
const blocksDir = os.homedir() + '/blocks/';
const txDir = os.homedir() + '/txs/';
if (!fs.existsSync(blocksDir)){
    fs.mkdirSync(blocksDir);
}
if (!fs.existsSync(txDir)){
    fs.mkdirSync(txDir);
}

// Write a JSON object to disk
function writeFile(index, element, dir){
  fs.writeFile(dir + index, JSON.stringify(element), function(err){
    if(!err){
      // delete files older than 20 blocks if it exists
      try {
        fs.unlinkSync(dir + (index-maxFiles));
      } catch(err) {
        console.log(err);
      }
    }
  });
}

// Get the SPV node object from the globally-installed bcoin package
const bcoin = require('bcoin');

// Configure the node for mainnet, write logs, use the database on disk, etc
const node = new bcoin.SPVNode({
  network: 'testnet',
  config: true,
  argv: true,
  env: true,
  logFile: true,
  logConsole: true,
  logLevel: 'debug',
  db: 'leveldb',
  memory: false,
  persistent: true,
  workers: true,
  listen: true,
  loader: require
});

// Add wallet and database
node.use(bcoin.wallet.plugin);


(async () => {

  // Validate the prefix directory (probably ~/.bcoin)
  await node.ensure();
  // Open the node and all its child objects, wait for the database to load
  await node.open();
  // Connect to the network
  await node.connect();
  
  // write new block details to file
  node.on('block', async (block) => {
    // most of the block's details are returned by the 'block' event but we need to get its height from the blockchain database
    headers = await node.chain.getEntryByHash(block.hash('hex'));
    blockHeight = headers.height;

    // simplify the block data structure to a string
    blockJSON = block.toJSON();

    // index it by height (orphaned blocks will therefore be replaced by new block at same height)
    writeFile(blockHeight, blockJSON, blocksDir);
  });

  // add wallet database
  const walletdb = node.require('walletdb').wdb;
  const wallet = await walletdb.primary;

  // write new transaction details to file named by tx hash in hex
  node.on('tx', async (tx) => {
    // add the tx to the database
    walletdb.addTX(tx);

    // get readable format for transaction message
    txJSON = tx.inspect();
    // discover which outputs of this tx belong to our wallet
    let details = []
    for (const output of txJSON.outputs) {
      let outputJSON = output.getJSON('main');
      if (await wallet.hasAddress(outputJSON.address))
        details.push(outputJSON);
    }
    // add "my output" list to object
    txJSON.details = details;
    fs.writeFile(txDir + txJSON.hash, JSON.stringify(txJSON), function(err){});
  });

  // Start the blockchain sync
  node.startSync();

})().catch((err) => {
  console.error(err.stack);
  process.exit(1);
});
