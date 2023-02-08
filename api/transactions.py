import itertools

import rich
import ujson

from aiohttp.client import (
    ClientSession, BasicAuth
)


class TransactionManager:
    json_loader = ujson.loads

    def __init__(self, rpcurl: str, auth: tuple[str, str], wallet: str, pk: str):
        self.rpcurl = rpcurl
        self.auth = BasicAuth(*auth)
        self.wallet = wallet
        self.private_key = pk

    async def send_coins(self, payable: list[dict[str, float]], fee: float = 0.01,) -> dict:
        unsigned_tx = None

        for fee in itertools.count(fee, 0.01):

            unsigned_tx = await self.create_raw_transaction(
                fee, payable
            )

            if unsigned_tx is None:
                continue

            break

        singed_tx = await self.sign_raw_transaction(
            unsigned_tx
        )

        return await self.send_raw_transaction(singed_tx)

    async def address_exists(self, address: str):
        result = await self.call_method("getaddressbalance", [address])
        rich.print(result)
        return result['error'] is None

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

    async def create_raw_transaction(self, fee: float, payable: list[dict[str, float]]) -> str:
        balance = await self.get_balance()
        utxo_list = await self.get_utxo()

        amount: float = 0
        for address in payable:
            amount += list(address.values())[0]

        method = await self.call_method("createrawtransaction", [
            [
                {"txid": utxo['txid'], "vout": utxo['outputIndex']} for utxo in utxo_list
            ],
            [*payable, {self.wallet: balance - amount - fee}]
        ])

        print(method)

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
    import asyncio

    async def main():
        sbercoin = TransactionManager(
            f"http://136.244.89.46:3889",
            ('SberUser', '32Xqb%7i8meM7xtoM?Y+'),
            'SY2kNKexBwJt1s7cd3KdphdPCGmVoSmbUN',
            '9toyp133wmyP9oaMnWs1nxy4zUuoCcS47MQr8NPjExxah9ygGeTh',
        )

        payable = [
            {'SVUt7GDHZrejN17XE8a2GEbACC8VAmn4sk': 5},
            {'SbF6jTu913JYGdQYnBWoezogp2fWJChGb8': 5},
        ]

        result = await sbercoin.send_coins(
            payable
        )

        rich.print(result)

    asyncio.run(main())

