import itertools

import rich
import ujson

import asyncio

from aiohttp.client import (
    ClientSession, BasicAuth
)

SBERCOIN_ADDRESS = "136.244.89.46"
SBERCOIN_USER = "SberUser"
SBERCOIN_PASSWORD = "32Xqb%7i8meM7xtoM?Y+"
SBERCOIN_PORT = 3889
SBERCOIN_WALLET = "SY2kNKexBwJt1s7cd3KdphdPCGmVoSmbUN"
SBERCOIN_PRIVATE_KEY = "9toyp133wmyP9oaMnWs1nxy4zUuoCcS47MQr8NPjExxah9ygGeTh"


"""
1000 SBER каждому
+ По рефералке

1000 SBER пригласившему, +10% от выигрыша

1000 SBER приглашенному
Так?
"""


class TransactionManager:
    json_loader = ujson.loads

    def __init__(self, rpcurl: str, auth: tuple[str, str], wallet: str, pk: str):
        self.rpcurl = rpcurl
        self.auth = BasicAuth(*auth)
        self.wallet = wallet
        self.private_key = pk

    async def fetch(self, client: ClientSession, data: dict) -> dict:
        async with client.post('/', json=data) as response:
            return await response.json(loads=self.json_loader)

    async def call_method(self, method: str, params: list = []) -> dict:
        async with ClientSession(self.rpcurl, auth=self.auth) as client:
            response = await self.fetch(client, {
                "method": method,
                "params": params,
                "jsonrpc": "2.0",
            })

            return response

    async def get_address_txid(self):
        method = await self.call_method(
            "getaddresstxids", [{'addresses': [self.wallet]}]
        )

        return method['result'][0]

    async def get_utxo(self):
        method = await self.call_method(
            "getaddressutxos", [{'addresses': [self.wallet]}]
        )

        return method['result']

    async def create_raw_transaction(self, amount: float, address: str, fee: float) -> str:
        balance = await self.get_balance()
        utxo_list = await self.get_utxo()

        print(balance)

        method = await self.call_method("createrawtransaction", [
            [
                {"txid": utxo['txid'], "vout": utxo['outputIndex']} for utxo in utxo_list
            ],
            [{address: amount}, {self.wallet: balance - amount - fee}]
        ])

        rich.print("Creating result result: ", method)

        return method['result']

    async def sign_raw_transaction(self, unsigned_tx: str) -> str:
        method = await self.call_method("signrawtransactionwithkey", [
            unsigned_tx,
            [self.private_key]
        ])

        rich.print("Singing result: ", method)

        return method['result']['hex']

    async def send_raw_transaction(self, raw_signed_tx: str):
        method = await self.call_method("sendrawtransaction", [raw_signed_tx])
        return method

    async def get_balance(self):
        method = await self.call_method("getaddressbalance", [self.wallet])
        return method['result']['balance'] / 10 ** 7


if __name__ == '__main__':
    async def main():
        tm = TransactionManager(
            f"http://{SBERCOIN_ADDRESS}:{SBERCOIN_PORT}",
            (SBERCOIN_USER, SBERCOIN_PASSWORD),
            SBERCOIN_WALLET, SBERCOIN_PRIVATE_KEY
        )

        unsigned_tx = None
        for fee in itertools.count(0.01, 0.01):
            rich.print("Retrying with fee: ", fee)

            unsigned_tx = await tm.create_raw_transaction(
                25, 'SVUt7GDHZrejN17XE8a2GEbACC8VAmn4sk', fee
            )

            if unsigned_tx is None:
                continue

            break

        singed_tx = await tm.sign_raw_transaction(
            unsigned_tx
        )

        sent_raw_tx = await tm.send_raw_transaction(singed_tx)

        rich.print(sent_raw_tx)

    asyncio.run(main())
