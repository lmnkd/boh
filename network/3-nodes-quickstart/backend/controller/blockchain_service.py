from blockchain.contract import get_contract
from blockchain.config import w3, ACCOUNT
from controller.controller import bytes32_from_value, tx_params

def propose_record(visit_id, data_hash, from_address=None):

    contract = get_contract()

    tx_hash = contract.functions.proposeRecord(
        visit_id,
        bytes32_from_value(data_hash)
    ).transact(tx_params(from_address or ACCOUNT))

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    return {
        "tx_hash": tx_hash.hex(),
        "receipt": dict(receipt)
    }


def vote_record(record_id, approve, from_address=None):

    contract = get_contract()

    tx_hash = contract.functions.vote(
        record_id,
        approve
    ).transact(tx_params(from_address or ACCOUNT))

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

    return {
        "tx_hash": tx_hash.hex(),
        "receipt": dict(receipt)
    }


def get_pending_records():
    contract = get_contract()
    return contract.functions.recordCount().call()