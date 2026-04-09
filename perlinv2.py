from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit.circuit.library import QFTGate
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import SamplerV2 as AerSamplerV2
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from scipy.ndimage import uniform_filter
from qiskit.circuit.library import StatePreparation
from distribution_generator import DistributionGenerator, make_distribution






g = DistributionGenerator(n_states=4, dist_type="random")

# Utilitaires
g.summary()              # tableau récap dans le terminal
g.plot()                 # histogramme matplotlib
a = g.simulate(shots=50_000)
print(a)