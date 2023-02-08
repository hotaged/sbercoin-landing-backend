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
        utxo = await self.get_utxo()

        method = await self.call_method("createrawtransaction", [
            [{"txid": utxo[0]['txid'], "vout": utxo[0]['outputIndex']}],
            [{address: amount}, {self.wallet: balance - amount - fee}]
        ])

        return method['result']

    async def sign_raw_transaction(self, unsigned_tx: str) -> str:
        method = await self.call_method("signrawtransactionwithkey", [
            unsigned_tx,
            [self.private_key]
        ])

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

        txid = await tm.get_address_txid()
        balance = await tm.get_balance()
        utxo = await tm.get_utxo()

        rich.print(txid)
        rich.print(utxo)

        unsinged_tx = await tm.create_raw_transaction(
            1.0, 'SVUt7GDHZrejN17XE8a2GEbACC8VAmn4sk', 0.01
        )

        singed_tx = await tm.sign_raw_transaction(
            unsinged_tx
        )

        sent_raw_tx = await tm.send_raw_transaction(singed_tx)

        rich.print(sent_raw_tx)

    asyncio.run(main())
