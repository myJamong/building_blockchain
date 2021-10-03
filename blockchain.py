import hashlib
import json
from textwrap import dedent
from time import time
from uuid import uuid4
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, request


class Blockchain:
    """
    Blockchain 클래스는 체인을 관리하는데 책임을 갖는다.
    트랜잭션을 저장하고 새로운 블록을 체인에 추가하는 helper method를 갖는다.
    """
    def __init__(self):
        self.chain = []
        self.current_transactions = []

        # 최초의 블록 생성
        self.new_block(previous_hash=1, proof=100)

        # Consensus Set
        self.nodes = set()

    def new_block(self, proof, previous_hash=None):
        """
        블록체인에 새로운 블록을 생성한다.
        :param proof: <int> 작업증명 알고리즘에의해 받은 Proof
        :param previous_hash: (Optional) <str> 이전 블록의 해시값
        :return: <dict> 새로운 블록
        """

        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }

        # 현재 트랜잭션 리스트를 초기화
        self.current_transactions = []

        self.chain.append(block)
        return block

    def new_transaction(self, sender, recipient, amount):
        """
        체인의 다음 마이닝 블록으로 들어갈 트랜잭션을 생성한다.
        :param sender: <str> 보내는 사람의 주소
        :param recipient: <str> 받는 사람의 주소
        :param amount: <int> 수량
        :return: <int> 해당 트랜잭션을 갖고 있을 블록의 index 값
        """

        self.current_transactions.append({
            'sender': sender,
            'recipient': recipient,
            'amount': amount,
        })

        return self.last_block['index'] + 1

    @property
    def last_block(self):
        """
        체인의 마지막 블록을 반환한다.
        :return: <dict> 마지막 블록
        """
        return self.chain[-1]

    @staticmethod
    def hash(block):
        """
        SHA-256 해시 블록을 생성한다.
        :param block: <dict> 블록
        :return: <str> 블록의 해시값
        """

        # 해시들이 순서를 갖는 것이 중요하여 딕셔너리가 순서를 갖도록하는 것이 중요하다.
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    def proof_of_work(self, last_proof):
        """
        간단한 작업증명 알고리즘
        - 숫자 p는 이전 Proof, p'는 현재 Proof
       - hash(pp')의 해시값의 마지막 4개 문자가 '0'인 p 값을 찾아라
        :param last_proof: <int>
        :return: <int>
        """

        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1
        return proof

    @staticmethod
    def valid_proof(last_proof, proof):
        """
        작업증명 검증 작업 : hash(last_proof, proof)에 마지막 4글자가 0인가?
        :param last_proof: <int> 이전 Proof
        :param proof: <int> 현재 Proof
        :return: <bool> 맞는 경우 True
        """

        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == '0000'

    def register_node(self, address):
        """
        노드 리스트에 새로운 노드를 추가한다.
        :param address: <str> 노드 주소 Ex) http://192.168.0.5:5000
        :return: None
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self, chain):
        """
        부여된 블록체인이 유효한지 검증
        :param chain: <list> 블록체인
        :return: <bool> 유효한 경우 True
        """

        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            print(f'{last_block}')
            print(f'{block}')
            print("\n---------------\n")

            # 블록의 해시가 맞는지 확인
            if block['previous_hash'] != self.hash(last_block):
                return False

            # 작업증명이 맞는지 확인
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    def resolve_conflicts(self):
        """
        Consensus 알고리즘으로 가장 오래된 체인으로 교체하여 충돌을 방지한다.
        :return: <bool> 체인이 교체된 경우 True
        """

        neighbours = self.nodes
        new_chain = None

        # 내가 소유한 체인보다 긴 체인들만 확인한다.
        max_length = len(self.chain)

        # 네트워크의 다른 노드들의 체인을 확인한다.
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']

                # 체인이 더 길고 유효한지 확인한다.
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain

        # 새로운 체인이 발견되었다면 교체한다.
        if new_chain:
            self.chain = new_chain
            return True

        return False


# 노드 인스턴스화
app = Flask(__name__)

# 전역적으로 고유한 주소를 해당 노드에 생성
node_identifier = str(uuid4()).replace('-', '.')

# 블록체인 인스턴스화
blockchain = Blockchain()


@app.route('/mine', methods=['GET'])
def mine():
    # 다음 Proof를 찾기 위헤 작업증명 알고리즘을 진행
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    # Proof를 찾은 것에 대한 보상이 있어야한다.
    blockchain.new_transaction(sender="0", recipient=node_identifier, amount=1)

    # 새 블록을 체인에 추가하여 구축?하다
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    response = {
        'message': "New Block Forged.",
        'index': block['index'],
        'transactions': block['transactions'],
        'proof': block['proof'],
        'previous_hash': block['previous_hash'],
    }
    return jsonify(response), 200


@app.route('/transactions/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    # POST에 필요한 인자가 있는지 확인
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400

    # 새로운 트랜잭션을 생성한다.
    index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

    response = {'message': f'Transaction will be added to Block {index}'}
    return jsonify(response), 201


@app.route('/chain', methods=['GET'])
def full_chain():
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200


@app.route('/node/register', methods=['POST'])
def register_nodes():
    values = request.get_json()

    nodes = values.get('nodes')
    if nodes is None:
        return "Error: Please supply a valid list of nodes", 400

    for node in nodes:
        blockchain.register_node(node)

    response = {
        'message': 'New nodes have been added',
        'total_nodes': list(blockchain.nodes),
    }
    return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain was authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=7000)
