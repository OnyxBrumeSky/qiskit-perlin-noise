from qiskit import QuantumCircuit, ClassicalRegister, QuantumRegister
from qiskit.circuit.library import QFTGate
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import SamplerV2 as AerSamplerV2
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from scipy.ndimage import uniform_filter

# ── 1. SEED → distribution N-dimensionnelle ───────────────────────────────────
def make_seed_distribution_nd(seed: int, n_gr: int, n_dims: int) -> np.ndarray:
    """
    Génère une distribution sur 2^(n_gr * n_dims) points.
    Chaque dimension a n_gr qubits GR → 2^n_gr bins par axe.
    """
    rng = np.random.default_rng(seed)
    total_bins = 2 ** (n_gr * n_dims)
    raw = rng.random(total_bins) + 0.05
    return raw / raw.sum()

# ── 2. CIRCUIT N-DIMENSIONNEL ─────────────────────────────────────────────────
def grover_rudolph_nd(p: np.ndarray, n_gr: int, n_qft: int, n_dims: int) -> QuantumCircuit:
    """
    n_dims registres GR de n_gr qubits chacun.
    n_dims registres QFT de n_qft qubits chacun.
    Total : n_dims * (n_gr + n_qft) qubits.
    """
    # Création des registres
    qr_gr  = [QuantumRegister(n_gr,  name=f'gr{i}')  for i in range(n_dims)]
    qr_qft = [QuantumRegister(n_qft, name=f'qft{i}') for i in range(n_dims)]
    cr     = ClassicalRegister(n_dims * (n_gr + n_qft), name='c')

    qc1 = QuantumCircuit(*qr_gr, *qr_qft)
    qc = QuantumCircuit(*qr_gr, *qr_qft, cr)

    # — GR sur l'état combiné de tous les registres —
    all_gr_qubits = [q for reg in qr_gr for q in reg]
    total_gr = n_gr * n_dims

    def encode_node(node_probs, qubits_left, controls):
        if not qubits_left:
            return
        qubit = qubits_left[0]
        mid   = len(node_probs) // 2
        p_l   = float(np.sum(node_probs[:mid]))
        p_r   = float(np.sum(node_probs[mid:]))
        total = p_l + p_r
        if total < 1e-10:
            return
        theta = 2 * np.arcsin(np.sqrt(np.clip(p_r / total, 0, 1)))
        if not controls:
            qc1.ry(theta, qubit)
        else:
            qc1.mcry(theta, controls, qubit)
        encode_node(node_probs[:mid], qubits_left[1:], controls + [qubit])
        encode_node(node_probs[mid:], qubits_left[1:], controls + [qubit])

    encode_node(p, all_gr_qubits, [])
    gate = qc1.to_gate()
    gate.name = "Grover Rodolph Gate"
    qc.compose(gate, inplace=True)

    # — QFT indépendante sur chaque registre dimensionnel —
    qc.barrier()
    for i in range(n_dims):
        qft = QFTGate(n_gr)
        qc.compose(qft, qr_gr[i], inplace=True)
        qc.swap(qr_gr[i][0], qr_qft[i][0])
        qc.swap(qr_gr[i][1], qr_qft[i][1])
        qc.cx(qr_gr[i][2], qr_gr[i][0])
        qc.cx(qr_gr[i][2], qr_gr[i][1])
        qft_gate = QFTGate(n_qft + n_gr)
        all_qr = qr_gr[i][:] + qr_qft[i][:]
        all_qr = all_qr[::-1] 
        qc.append(qft_gate, all_qr)
    
    qc.barrier()
    # — Mesures : GR puis QFT pour chaque dimension —
    bit_offset = 0
    for i in range(n_dims):
        qc.measure(qr_gr[i],  cr[bit_offset : bit_offset + n_gr])
        bit_offset += n_gr
        qc.measure(qr_qft[i], cr[bit_offset : bit_offset + n_qft])
        bit_offset += n_qft

    return qc

# ── 3. SIMULATION ─────────────────────────────────────────────────────────────
def simulate(circuit: QuantumCircuit, shots: int = 4096) -> dict:
    backend = AerSimulator(method="statevector")
    pm      = generate_preset_pass_manager(target=backend.target, optimization_level=3)
    qc_isa  = pm.run(circuit)
    job     = AerSamplerV2().run([qc_isa], shots=shots)
    return job.result()[0].data.c.get_counts()

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
def plot_2d(noise_map: np.ndarray, seed: int, smooth_size: int = 3):
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
    fig.suptitle(f"Quantum Perlin Noise 2D — seed={seed}", fontsize=14)

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

# ── 6. PIPELINE PRINCIPAL ─────────────────────────────────────────────────────
def quantum_perlin_nd(seed: int, n_gr: int = 3, n_qft: int = 2,
                      n_dims: int = 2, shots: int = 4096):
    print(f"Seed={seed} | {n_dims}D | GR={n_gr} qubits/dim | QFT={n_qft} qubits/dim")
    print(f"Total qubits : {n_dims * (n_gr + n_qft)} | "
          f"Carte : {2**(n_gr+n_qft)}^{n_dims} = {2**(n_dims*(n_gr+n_qft))} cases")

    p = make_seed_distribution_nd(seed, n_gr, n_dims)
    qc = grover_rudolph_nd(p, n_gr, n_qft, n_dims)
    print(f"Circuit : {qc.num_qubits} qubits, {qc.depth()} couches")
    display(qc.draw(output="mpl"))

    counts = simulate(qc, shots)
    #print(counts)
    tensor = counts_to_nd_tensor(counts, n_gr, n_qft, n_dims)
    if n_dims == 2:
        plot_2d(tensor, seed)
    elif n_dims == 1:
        plt.figure(figsize=(10, 3))
        plt.plot(tensor, color='steelblue', linewidth=2)
        plt.fill_between(range(len(tensor)), tensor, alpha=0.3)
        plt.title(f"Quantum Perlin Noise 1D — seed={seed}")
        plt.tight_layout(); plt.show()
    else:
        print(f"Tenseur {n_dims}D shape={tensor.shape}, sum={tensor.sum():.4f}")
        # Slice 2D pour visualiser une coupe
        plot_2d(tensor[..., 0], seed, smooth_size=2)

    signal(counts, n_gr, n_qft, shots, seed, p, n_dims)
    
    return tensor


def counts_to_signal(counts: dict, total_qubits: int, shots: int) -> np.ndarray:
    n_bins = 2 ** total_qubits
    signal = np.zeros(n_bins)
    for bitstring, count in counts.items():
        idx = int(bitstring, 2)
        signal[idx] = count / shots
    return signal


def signal(counts, n_gr, n_qft, shots, seed, p, n_dims):
    # Signal
    signal = counts_to_signal(counts, (n_gr + n_qft) * n_dims, shots)

    # — Visualisation —
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    fig.suptitle(f"Quantum Perlin Noise 1D — seed={seed}", fontsize=13)

    axes[0].bar(range(len(p)), p, color='steelblue')
    axes[0].set_title("Distribution d'entrée (seed classique)")
    axes[0].set_xlabel("bin"); axes[0].set_ylabel("probabilité")

    axes[1].bar(range(len(signal)), signal, color='darkorange')
    axes[1].set_title(f"Sortie GR+QFT ({n_gr+n_qft} qubits, {2**(n_gr+n_qft)} bins)")
    axes[1].set_xlabel("état"); axes[1].set_ylabel("fréquence")

    # Lissage final (comme Perlin noise)
    from scipy.ndimage import uniform_filter1d
    smoothed = uniform_filter1d(signal, size=4)
    axes[2].plot(smoothed, color='seagreen', linewidth=2)
    axes[2].fill_between(range(len(smoothed)), smoothed, alpha=0.3, color='seagreen')
    axes[2].set_title("Signal lissé (Quantum Perlin Noise)")
    axes[2].set_xlabel("x"); axes[2].set_ylabel("amplitude")

    plt.tight_layout()
    plt.show()
    return signal

# ── 7. DEMO ───────────────────────────────────────────────────────────────────
# Carte 2D (10 qubits : 2×3 GR + 2×2 QFT)
map_2d = quantum_perlin_nd(seed=3, n_gr=3, n_qft=2, n_dims=2, shots=500)

