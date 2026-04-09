import numpy as np
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import StatePreparation
from qiskit_aer import AerSimulator
from distribution_generator import DistributionGenerator
#from qft import apply_qft_interpolation
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.library import QFTGate
from scipy.ndimage import uniform_filter
from matplotlib.colors import ListedColormap

def apply_qft_interpolation(
    qc: QuantumCircuit,
    n_dim: int,
    n_ancilla: int,
    measure: bool = True
) -> QuantumCircuit:
    """
    Découpe le circuit en n_dim morceaux de taille égale,
    ajoute n_ancilla qubits ancilla par morceau,
    applique :
      1. QFT locale sur le morceau
      2. QFT globale sur (morceau + ancilla)
      3. mesure optionnelle

    Paramètres
    ----------
    qc : QuantumCircuit
        Circuit existant contenant les qubits de données.
    n_dim : int
        Nombre de morceaux.
    n_ancilla : int
        Nombre d’ancilla à ajouter par morceau.
    measure : bool
        Si True, mesure tous les qubits.

    Retour
    ------
    QuantumCircuit
        Nouveau circuit avec interpolation QFT.
    """

    total_data = qc.num_qubits

    if total_data % n_dim != 0:
        raise ValueError(
            f"Le nombre de qubits ({total_data}) doit être divisible par n_dim ({n_dim})."
        )

    chunk_size = total_data // n_dim

    # Nouveau registre ancilla
    anc_regs = [
        QuantumRegister(n_ancilla, name=f"anc{i}")
        for i in range(n_dim)
    ]

    # Nouveau circuit avec anciens qubits + ancilla
    new_qc = QuantumCircuit(*qc.qregs)

    for anc in anc_regs:
        new_qc.add_register(anc)

    # recopier le circuit original
    new_qc.compose(qc, inplace=True)

    print(chunk_size)
    # mesure optionnelle
    #if measure:
    #    creg = ClassicalRegister(new_qc.num_qubits)
    #    new_qc.add_register(creg)
    # mesure optionnelle
    if measure:
        creg = [ClassicalRegister(chunk_size + n_ancilla) for i in range(n_dim)]
        for reg in creg :
            new_qc.add_register(reg)
    # interpolation QFT par bloc
    for i in range(n_dim):
        start = i * chunk_size
        end = (i + 1) * chunk_size

        # bloc courant
        data_block = new_qc.qubits[start:end]
        anc_block = list(anc_regs[i])

        # 1. QFT locale sur les qubits du bloc
        qft_local = QFTGate(chunk_size)
        new_qc.append(qft_local, data_block)

        # 2. mélange simple avec ancilla (copie de structure fréquentielle)
        for j in range(min(chunk_size, n_ancilla)):
            new_qc.swap(data_block[j], anc_block[j])

        control = data_block[-1]
        for target in data_block[:-1]:
            new_qc.cx(control, target)
        
        # 3. QFT globale sur bloc + ancilla
        full_block = data_block + anc_block
        full_block = full_block[::-1]  # optionnel : ordre little-endian propre

        qft_interp = QFTGate(len(full_block))
        new_qc.append(qft_interp, full_block)

        # mesure optionnelle
        if measure:
            full_block = full_block[::-1]
            new_qc.measure(full_block, creg[i])

    return new_qc


# ─────────────────────────────────────────────
# 1. Générer une distribution avec ton générateur
# ─────────────────────────────────────────────

g = DistributionGenerator(n_states=6, dist_type="random")

# Affichage utile
#g.summary()
g.plot()

# Distribution cible
probabilities = g.probabilities   # ou g.distribution selon ton implémentation

# Vérification
assert np.isclose(probabilities.sum(), 1.0), "La distribution doit sommer à 1"

n_states = len(probabilities)
n_qubits = int(np.ceil(np.log2(n_states))) # determine with 2'n = nb states

#print(f"\nDistribution cible : {probabilities.round(4)}")
#print(f"Nombre d'états      : {n_states}")
#print(f"Nombre de qubits    : {n_qubits}")

# ─────────────────────────────────────────────
# 2. Préparer les amplitudes quantiques
# ─────────────────────────────────────────────

amplitudes = np.sqrt(probabilities)

# padding si besoin
full_size = 2 ** n_qubits
if n_states < full_size:
    amplitudes = np.pad(amplitudes, (0, full_size - n_states))

# normalisation sécurité
amplitudes = amplitudes / np.linalg.norm(amplitudes)

#print(f"\nAmplitudes : {amplitudes.round(4)}")

# ─────────────────────────────────────────────
# 3. Construire le circuit
# ─────────────────────────────────────────────

qc = QuantumCircuit(n_qubits)

state_prep = StatePreparation(amplitudes)
state_prep.label = "State Prep" 
qc.append(state_prep, range(n_qubits))
#qc.measure_all()

qc = apply_qft_interpolation(qc, n_dim=2, n_ancilla=2, measure = True)



print("\nCircuit quantique :")
#print(qc.draw(output="text", fold=80))
display(qc.draw(output="mpl"))

# ─────────────────────────────────────────────
# 4. Simulation quantique
# ─────────────────────────────────────────────

simulator = AerSimulator()
shots = 50_000

transpiled = transpile(qc, simulator)
job = simulator.run(transpiled, shots=shots)
counts = job.result().get_counts()

#print(counts)

# ── 4. COUNTS → TENSEUR N-DIMENSIONNEL ───────────────────────────────────────
def counts_to_nd_tensor(counts: dict, n_gr: int, n_qft: int, n_dims: int) -> np.ndarray:
    """
    Chaque bitstring est découpé en n_dims blocs de (n_gr + n_qft) bits.
    On construit un tenseur de shape (bins_per_dim,) * n_dims.
    """
    bits_per_dim = n_gr + n_qft
    bins_per_dim = 2 ** bits_per_dim
    shape = tuple([bins_per_dim] * n_dims)
    tensor = np.zeros(shape)

    total = sum(counts.values())
    for bitstring, count in counts.items():
        # Qiskit renvoie les bits dans l'ordre inverse
        bits = bitstring.replace(" ", "")[::-1]
        indices = []
        for d in range(n_dims):
            chunk = bits[d * bits_per_dim : (d + 1) * bits_per_dim]
            indices.append(int(chunk[::-1], 2))
        tensor[tuple(indices)] += count / total

    return tensor

# ── 5. VISUALISATION 2D ───────────────────────────────────────────────────────
def plot_2d(noise_map: np.ndarray, smooth_size: int = 3):
    smoothed = uniform_filter(noise_map, size=smooth_size)

    # Biome : seuils sur les quantiles
    q = np.quantile(smoothed, [0.15, 0.35, 0.55, 0.75, 0.90])
    biome = np.zeros_like(smoothed, dtype=int)
    biome[smoothed > q[0]] = 1   # plage
    biome[smoothed > q[1]] = 2   # plaine
    biome[smoothed > q[2]] = 3   # forêt
    biome[smoothed > q[3]] = 4   # montagne
    biome[smoothed > q[4]] = 5   # neige

    biome_colors = ['#1a6691', '#f5deb3', '#90c060', '#228b22', '#888888', '#ffffff']
    biome_labels = ['Eau',     'Plage',   'Plaine',  'Forêt',  'Montagne', 'Neige']
    cmap = ListedColormap(biome_colors)

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(f"Quantum Perlin Noise 2D", fontsize=14)

    axes[0].imshow(noise_map, cmap='gray', interpolation='nearest')
    axes[0].set_title("Distribution brute GR+QFT")
    axes[0].axis('off')

    axes[1].imshow(smoothed, cmap='gray', interpolation='bilinear')
    axes[1].set_title("Distribution lissée")
    axes[1].axis('off')

    im = axes[2].imshow(biome, cmap=cmap, vmin=0, vmax=5, interpolation='nearest')
    axes[2].set_title("Carte de biomes")
    axes[2].axis('off')
    patches = [plt.Rectangle((0,0),1,1, color=biome_colors[i]) for i in range(6)]
    axes[2].legend(patches, biome_labels, loc='lower right', fontsize=8)

    plt.tight_layout()
    plt.show()



tensor = counts_to_nd_tensor(counts, 3, 2, 2)
plot_2d(tensor,)


bitstrings = sorted(counts.keys())  # trie alphabétiquement
counts_sorted = [counts[b] for b in bitstrings]

# Graphique
plt.figure(figsize=(12, 4))
plt.bar(range(len(counts_sorted)), counts_sorted, color='steelblue', alpha=0.85)
plt.xticks(range(len(counts_sorted)), bitstrings, rotation=90)
plt.xlabel("État binaire")
plt.ylabel("Counts")
plt.title("Histogramme des counts Qiskit")
plt.tight_layout()
plt.show()
