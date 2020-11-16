import json
import logging
import numpy as np
import warnings

from functools import wraps
from typing import Any, Callable, Optional, Tuple, Union


from qiskit import IBMQ, QuantumCircuit, assemble
from qiskit.circuit import Gate
from qiskit.circuit.library import UGate, U3Gate, CXGate
from qiskit.providers.ibmq import AccountProvider, IBMQProviderError
from qiskit.providers.ibmq.job import IBMQJob


def get_provider() -> AccountProvider:
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')

        ibmq_logger = logging.getLogger('qiskit.providers.ibmq')
        current_level = ibmq_logger.level
        ibmq_logger.setLevel(logging.ERROR)

        # get provider
        try:
            provider = IBMQ.get_provider()
        except IBMQProviderError:
            provider = IBMQ.load_account()

        ibmq_logger.setLevel(current_level)
        return provider


def get_job(job_id: str) -> Optional[IBMQJob]:
    try:
        job = get_provider().backends.retrieve_job(job_id)
        return job
    except Exception:
        pass

    return None


def circuit_to_json(qc: QuantumCircuit) -> str:
    class _QobjEncoder(json.encoder.JSONEncoder):
        def default(self, obj: Any) -> Any:
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, complex):
                return (obj.real, obj.imag)
            return json.JSONEncoder.default(self, obj)

    return json.dumps(circuit_to_dict(qc), cls=_QobjEncoder)


def circuit_to_dict(qc: QuantumCircuit) -> dict:
    qobj = assemble(qc)
    return qobj.to_dict()


def get_job_urls(job: Union[str, IBMQJob]) -> Tuple[bool, Optional[str], Optional[str]]:
    try:
        job_id = job.job_id() if isinstance(job, IBMQJob) else job
        download_url = get_provider()._api_client.account_api.job(job_id).download_url()['url']
        result_url = get_provider()._api_client.account_api.job(job_id).result_url()['url']
        return download_url, result_url
    except Exception:
        return None, None


def cached(key_function: Callable) -> Callable:
    def _decorator(f: Any) -> Callable:
        f.__cache = {}
        @wraps(f)
        def _decorated(*args: Any, **kwargs: Any) -> int:
            key = key_function(*args, **kwargs)
            if key not in f.__cache:
                f.__cache[key] = f(*args, **kwargs)
            return f.__cache[key]
        return _decorated
    return _decorator


def gate_key(gate: Gate) -> Tuple[str, int]:
    return gate.name, gate.num_qubits


@cached(gate_key)
def gate_cost(gate: Gate) -> int:
    if isinstance(gate, UGate):
        return 1
    elif isinstance(gate, U3Gate):
        return 1
    elif isinstance(gate, CXGate):
        return 10
    return sum(map(gate_cost, (g for g, _, _ in gate.definition.data)))


def compute_cost(circuit: QuantumCircuit) -> int:
    print('Computing cost...')
    return sum(map(gate_cost, (g for g, _, _ in circuit.data if isinstance(g, Gate))))


def has_cx(circuit: QuantumCircuit) -> bool:
    return any(isinstance(g, CXGate) for g, _, _ in circuit.data)
