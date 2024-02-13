from web3 import Web3, HTTPProvider
import sys
import os
import toml
settings = toml.load("settings.toml")
import json
from typing import Dict, List, Tuple
import time
import gc
import random

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))
from fetchPackage.StackCarpenter import stackCarpener
from utilsPackage.compressor import writeCompressedJson, readCompressedJson


class fetcher:
    def __init__(self):
        self.urls = settings["settings"]["rpcProviders"]

        self.w3s = []
        for url in self.urls:
            self.w3s.append(Web3(HTTPProvider(url, request_kwargs={'timeout': 60})))        
        self.counter = random.randint(0, len(self.urls))
        self.stackCarpenter = stackCarpener()
        self.debug_traceTransactionSettings = {
            'enableMemory': True,
            "disableMemory": False,
            'disableStack': False,
            'disableStorage': True,
            'enableReturnData': False,
        }
        self.results = []

    def get_url(self):
        self.counter += 1
        numOfUrls = len(self.urls)
        return self.urls[self.counter % numOfUrls]

    def get_w3(self):
        self.counter += 1
        numOfUrls = len(self.urls)
        return self.w3s[self.counter % numOfUrls]

    def pruneStructLog(self, structLog: dict, lastOpcode: str = None, FullTrace: bool = False):
        structLog_copy = structLog.copy()
        prune1 = True 
        prune2 = True # still need it, otherwise exceed 100MB file size limit
        if FullTrace:
            prune1 = False
            prune2 = False

        # Prune 1: remove pc, and gasCost
        if prune1:
            # del structLog_copy["pc"]
            # del structLog_copy["gas"]
            # del structLog_copy["depth"]
            del structLog_copy["gasCost"]

        # Prune 2: remove unnessary stack (won't be used by opcode)
        if prune2:
            len1 = self.stackCarpenter.opcode2InputStackLength(structLog_copy["op"])
            len2 = 0
            if lastOpcode != None:
                len2 = self.stackCarpenter.opcode2OutputStackLength(lastOpcode)
            necessaryStackLen = max(len1, len2)
            del structLog_copy["stack"][:-necessaryStackLen]

        if "error" in structLog_copy:
            error_dict = dict(structLog_copy["error"]).copy()
            structLog_copy["error"] = error_dict

        # Prune 3: remove unnessary memory (won't be used by opcode)
        if structLog_copy["op"] == "RETURN" \
            or structLog_copy["op"] == "REVERT" \
            or structLog_copy["op"] == "KECCAK256" \
            or structLog_copy["op"] == "CODECOPY" \
            or structLog_copy["op"] == "EXTCODECOPY" \
            or structLog_copy["op"] == "RETURNDATACOPY" \
            or structLog_copy["op"] == "SHA3" :
            pass
        elif structLog_copy["op"] == "CREATE" or structLog_copy["op"] == "CREATE2" or \
            structLog_copy["op"] == "CALL" or structLog_copy["op"] == "CALLCODE" or \
            structLog_copy["op"] == "STATICCALL" or structLog_copy["op"] == "DELEGATECALL":
            pass
        elif lastOpcode == "CALLDATACOPY" or lastOpcode == "CODECOPY" or lastOpcode == "EXTCODECOPY" or \
                lastOpcode == "RETURNDATACOPY":
            pass
        elif lastOpcode == "CALL" or lastOpcode == "CALLCODE" or lastOpcode == "STATICCALL" or lastOpcode == "DELEGATECALL":
            pass
        else:
            if "memory" in structLog_copy:
                del structLog_copy["memory"]
        return structLog_copy




    def getTrace(self, Tx: str, FullTrace: bool = False):
        """Given a tx hash, return the trace data"""
        web3 = self.get_w3()
        start = time.time()
        gc.collect()
        print(Tx)
        result = None
        try: 
            result = web3.manager.request_blocking('debug_traceTransaction', [Tx, self.debug_traceTransactionSettings])
        except MemoryError:
            print("MemoryError when collecting trace data " + Tx, file=sys.stderr)

        end = time.time() - start
        print("Tx {} fetch trace costs {} s".format(Tx[0:4], end))
        
        result_dict = self.cookResult(result, FullTrace=FullTrace)
        print("Tx {} cooking trace costs {} s".format(Tx[0:4], time.time() - start - end))
        return result_dict
        
    def cookResult(self, result, FullTrace: bool = False):
        result_dict = dict(result)
        lastOpcode = {} # last opcode of the same depth
        for ii in range(len(result_dict['structLogs'])):
            structLog = result_dict['structLogs'][ii]
            structLog_dict = dict(structLog)
            depth = structLog_dict['depth']
            if depth not in lastOpcode:
                structLog_dict_copy = self.pruneStructLog(structLog_dict, FullTrace=FullTrace)
            else:
                structLog_dict_copy = self.pruneStructLog(structLog_dict, lastOpcode[depth], FullTrace=FullTrace)
            result_dict['structLogs'][ii] = structLog_dict_copy
            lastOpcode[depth] = structLog_dict_copy["op"]
        return result_dict


def main():
    fe = fetcher()
    # HackTx = "0x395675b56370a9f5fe8b32badfa80043f5291443bd6c8273900476880fb5221e"
    # fe.storeTrace("DeFiHackLabs", "0x051ebd717311350f1684f89335bed4abd083a2b6", HackTx, True )

    ## TxSpector Example
    HackTx = "0x37085f336b5d3e588e37674544678f8cb0fc092a6de5d83bd647e20e5232897b"

    result_dict = fe.getTrace(HackTx, FullTrace=False)
    # store it in a json file
    with open("TxSpectorExample.json", "w") as f:
        json.dump(result_dict, f, indent=2)






if __name__ == "__main__":
    main()


