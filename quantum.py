from qiskit import QuantumCircuit
from qiskit.primitives import BackendSamplerV2
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel 
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
import sys
from qiskit.visualization import plot_histogram
from qiskit.quantum_info import Statevector
from qiskit.visualization import plot_bloch_multivector
import math


def circuit(seed):
    circuit = QuantumCircuit(2,2)
    circuit.h(0)
    
    circuit.rx(seed[0],0)
    circuit.rz(seed[1],0)
    circuit.ry(seed[2],0)

    circuit.cx(0,1)
    circuit.h(1)
    circuit.h(0)
    state = Statevector(circuit)
    circuit.measure([0, 1], [0, 1])
    return (state, circuit)


def simulation(circuit, shots):
    backend_sim = AerSimulator(method="statevector")
    sampler_sim = BackendSamplerV2(backend=backend_sim)
    
    target = backend_sim.target
    pm = generate_preset_pass_manager(target=target, optimization_level=3)
    
    qc_isa = pm.run(circuit)
    job = sampler_sim.run([qc_isa],shots=shots)
    
    res = job.result()
    return res



def prints_stats(res, shots):
    statistics = res[0].data.c.get_counts()
    
    for key in statistics:
        statistics[key] = float(statistics[key]) / shots
    display(plot_histogram(statistics))

for i in range(8):
    for j in range(8):
        for k in range(8):
            seed = [math.radians(i * step), math.radians(j * step), math.radians(k * step)]
            (state, c) = circuit(seed)  # ton circuit renvoie le statevector
            lst.append(state)

# Afficher chaque état un par un
for idx, elem in enumerate(lst):
    clear_output(wait=True)       # nettoie la sortie précédente (optionnel)
    print(f"État {idx + 1} / {len(lst)}")
    display(plot_bloch_multivector(elem))  # afficher la sphère de Bloch
    input("Appuyez sur Entrée pour passer au suivant...")