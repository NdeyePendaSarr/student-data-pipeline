import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, X } from 'lucide-react';
import { MATIERES, libelleMatiere, note } from '../api.js';
import { Bouton, Champ, Liste } from './Ui.jsx';

const vide = () =>
    Object.fromEntries(MATIERES.map((m) => [m, { devoirs: '', examen: '' }]));

/**
 * Aperçu de la moyenne d'une matière, avec la formule du serveur
 * (backend/app/regles.py) : devoirs pour un tiers, examen pour deux
 * tiers. Le serveur recalcule de toute façon la valeur enregistrée.
 */
function moyenneMatiere(saisie) {
    const devoirs = saisie.devoirs
        .split(',')
        .map((n) => parseFloat(n.trim().replace(',', '.')))
        .filter((n) => !Number.isNaN(n));
    const examen = parseFloat(String(saisie.examen).replace(',', '.'));

    if (!devoirs.length || Number.isNaN(examen)) return null;
    const moyDevoirs = devoirs.reduce((a, b) => a + b, 0) / devoirs.length;
    return { devoirs, examen, moyenne: (moyDevoirs + 2 * examen) / 3 };
}

export default function FormulaireEleve({ classes, onFermer, onEnregistrer }) {
    const [champs, setChamps] = useState({
        code: '', numero: '', nom: '', prenom: '',
        date_naissance: '', classe: ''
    });
    const [notes, setNotes]       = useState(vide);
    const [erreurs, setErreurs]   = useState({});
    const [envoi, setEnvoi]       = useState(false);
    const premierChamp            = useRef(null);

    useEffect(() => {
        premierChamp.current?.focus();
        const surEchap = (e) => e.key === 'Escape' && onFermer();
        window.addEventListener('keydown', surEchap);
        return () => window.removeEventListener('keydown', surEchap);
    }, [onFermer]);

    const moyennes = useMemo(
        () =>
            Object.fromEntries(
                MATIERES.map((m) => [m, moyenneMatiere(notes[m])])
            ),
        [notes]
    );

    const majChamp = (cle) => (e) =>
        setChamps((c) => ({ ...c, [cle]: e.target.value }));

    const majNote = (matiere, cle) => (e) =>
        setNotes((n) => ({
            ...n,
            [matiere]: { ...n[matiere], [cle]: e.target.value }
        }));

    function valider() {
        const trouvees = {};
        if (!/^[A-Z]{3}[0-9]{3}$/.test(champs.code))
            trouvees.code = 'Trois lettres majuscules puis trois chiffres, comme AAD004.';
        if (!/^[A-Z0-9]{7}$/.test(champs.numero.toUpperCase()))
            trouvees.numero = 'Sept caractères, lettres et chiffres.';
        if (champs.nom.trim().length < 2)
            trouvees.nom = 'Au moins deux caractères.';
        if (champs.prenom.trim().length < 3)
            trouvees.prenom = 'Au moins trois caractères.';
        if (!champs.date_naissance)
            trouvees.date_naissance = 'Date requise.';
        if (!champs.classe) trouvees.classe = 'Classe requise.';

        for (const m of MATIERES) {
            const saisie = notes[m];
            const remplie = saisie.devoirs.trim() || String(saisie.examen).trim();
            if (!remplie) continue;

            const calcul = moyennes[m];
            if (!calcul) {
                trouvees[`note_${m}`] =
                    `${libelleMatiere(m)} : renseignez les devoirs et l'examen.`;
                continue;
            }
            const hors = [...calcul.devoirs, calcul.examen].find(
                (n) => n < 0 || n > 20
            );
            if (hors !== undefined)
                trouvees[`note_${m}`] =
                    `${libelleMatiere(m)} : ${hors} est en dehors de 0 à 20.`;
        }

        setErreurs(trouvees);
        return Object.keys(trouvees).length === 0;
    }

    async function enregistrer() {
        if (!valider()) return;
        setEnvoi(true);

        const notesRetenues = {};
        for (const m of MATIERES) {
            const calcul = moyennes[m];
            if (calcul) {
                notesRetenues[m] = {
                    devoirs: calcul.devoirs,
                    examen:  calcul.examen,
                    moyenne: Number(calcul.moyenne.toFixed(2))
                };
            }
        }

        try {
            await onEnregistrer({
                ...champs,
                numero: champs.numero.toUpperCase(),
                notes:  notesRetenues
            });
        } finally {
            setEnvoi(false);
        }
    }

    const listeErreurs = Object.entries(erreurs).filter(([c]) =>
        c.startsWith('note_')
    );

    return (
        <div
            className="fixed inset-0 z-40 flex items-start justify-center
                       overflow-y-auto bg-texte/45 p-4 backdrop-blur-[2px]"
            onMouseDown={(e) => e.target === e.currentTarget && onFermer()}
        >
            <div
                role="dialog"
                aria-modal="true"
                aria-label="Ajouter un élève"
                className="my-6 w-full max-w-2xl rounded-xl border border-bordure
                           bg-surface"
            >
                <header className="border-b border-bordure px-6 py-4">
                    <h2 className="text-[19px]">Ajouter un élève</h2>
                    <p className="mt-0.5 text-[13px] text-sourdine">
                        Les notes sont facultatives. Pour être prises en compte,
                        une matière demande ses devoirs et sa note d'examen.
                    </p>
                </header>

                <div className="space-y-5 px-6 py-5">
                    <div className="grid gap-4 sm:grid-cols-2">
                        <Champ
                            ref={premierChamp}
                            etiquette="Code"
                            placeholder="AAD004"
                            value={champs.code}
                            onChange={majChamp('code')}
                            erreur={erreurs.code}
                        />
                        <Champ
                            etiquette="Numéro"
                            placeholder="H5G32YR"
                            value={champs.numero}
                            onChange={majChamp('numero')}
                            erreur={erreurs.numero}
                        />
                        <Champ
                            etiquette="Nom"
                            value={champs.nom}
                            onChange={majChamp('nom')}
                            erreur={erreurs.nom}
                        />
                        <Champ
                            etiquette="Prénom"
                            value={champs.prenom}
                            onChange={majChamp('prenom')}
                            erreur={erreurs.prenom}
                        />
                        <Champ
                            etiquette="Date de naissance"
                            type="date"
                            value={champs.date_naissance}
                            onChange={majChamp('date_naissance')}
                            erreur={erreurs.date_naissance}
                        />
                        <Liste
                            etiquette="Classe"
                            value={champs.classe}
                            onChange={majChamp('classe')}
                            erreur={erreurs.classe}
                            options={[
                                { valeur: '', texte: 'Choisir une classe' },
                                ...classes.map((c) => ({ valeur: c, texte: c }))
                            ]}
                        />
                    </div>

                    <div>
                        <h3 className="mb-2 text-[13.5px] font-semibold">
                            Notes par matière
                        </h3>
                        <div className="overflow-hidden rounded-lg border border-bordure">
                            <table className="w-full border-collapse">
                                <thead>
                                    <tr className="border-b border-bordure bg-fond text-[12px] text-sourdine">
                                        <th className="px-3 py-2 text-left font-medium">
                                            Matière
                                        </th>
                                        <th className="px-3 py-2 text-left font-medium">
                                            Devoirs
                                        </th>
                                        <th className="px-3 py-2 text-left font-medium">
                                            Examen
                                        </th>
                                        <th className="px-3 py-2 text-right font-medium">
                                            Moyenne
                                        </th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-bordure">
                                    {MATIERES.map((m) => (
                                        <tr key={m}>
                                            <td className="px-3 py-2 text-[13px]">
                                                {libelleMatiere(m)}
                                            </td>
                                            <td className="px-3 py-2">
                                                <input
                                                    placeholder="12, 14, 10"
                                                    value={notes[m].devoirs}
                                                    onChange={majNote(m, 'devoirs')}
                                                    className="w-full rounded-md border border-bordure
                                                               px-2 py-1 text-[13px]
                                                               placeholder:text-sourdine/70
                                                               focus:border-primaire focus:outline-none"
                                                />
                                            </td>
                                            <td className="px-3 py-2">
                                                <input
                                                    placeholder="0 à 20"
                                                    value={notes[m].examen}
                                                    onChange={majNote(m, 'examen')}
                                                    className="w-full rounded-md border border-bordure
                                                               px-2 py-1 text-[13px]
                                                               placeholder:text-sourdine/70
                                                               focus:border-primaire focus:outline-none"
                                                />
                                            </td>
                                            <td className="chiffres px-3 py-2 text-right text-[13px] font-semibold">
                                                {moyennes[m]
                                                    ? note(moyennes[m].moyenne)
                                                    : '—'}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        {listeErreurs.length > 0 && (
                            <ul className="mt-2 space-y-0.5">
                                {listeErreurs.map(([cle, texte]) => (
                                    <li key={cle} className="text-[12px] text-alerte">
                                        {texte}
                                    </li>
                                ))}
                            </ul>
                        )}
                    </div>
                </div>

                <footer className="flex justify-end gap-2 border-t border-bordure px-6 py-4">
                    <Bouton onClick={onFermer} disabled={envoi}>
                        <X size={15} strokeWidth={2.4} /> Annuler
                    </Bouton>
                    <Bouton variante="principal" onClick={enregistrer} disabled={envoi}>
                        <Check size={15} strokeWidth={2.4} />
                        {envoi ? 'Enregistrement…' : 'Enregistrer'}
                    </Bouton>
                </footer>
            </div>
        </div>
    );
}
