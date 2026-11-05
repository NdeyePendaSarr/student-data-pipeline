# ============================================
# models/etudiant.py
# ============================================
from datetime import date

from pydantic import BaseModel, Field, field_validator, model_validator

from app.regles import code_valide, moyenne_matiere, numero_valide


def normaliser_nom(v: str) -> str:
    v = v.strip()
    if len(v) < 2 or not v[0].isalpha():
        raise ValueError(
            'Le nom doit faire 2 caractères et commencer par une lettre'
        )
    return v.upper()


def normaliser_prenom(v: str) -> str:
    v = v.strip()
    if len(v) < 3 or not v[0].isalpha():
        raise ValueError(
            'Le prénom doit faire 3 caractères et commencer par une lettre'
        )
    return v.title()


class NoteMatiere(BaseModel):
    """
    Notes pour une matière.
    devoirs : liste de notes de devoirs
    examen  : note d'examen
    moyenne : toujours recalculée par le serveur ; une valeur
              envoyée par le client est ignorée.
    """
    devoirs: list[float]   = Field(..., min_length=1)
    examen:  float         = Field(..., ge=0, le=20)
    moyenne: float | None  = None

    @field_validator('devoirs')
    @classmethod
    def valider_devoirs(cls, v):
        for note in v:
            if note < 0 or note > 20:
                raise ValueError(
                    f'Note {note} invalide — '
                    f'doit être entre 0 et 20'
                )
        return v

    @model_validator(mode='after')
    def calculer_moyenne(self):
        self.moyenne = moyenne_matiere(self.devoirs, self.examen)
        return self


class EtudiantCreer(BaseModel):
    """
    Modèle complet pour la création d'un étudiant avec ses notes.
    """
    code:           str  = Field(..., min_length=6, max_length=6)
    numero:         str  = Field(..., min_length=7, max_length=7)
    nom:            str  = Field(..., min_length=2)
    prenom:         str  = Field(..., min_length=3)
    date_naissance: date
    classe:         str
    notes:          dict[str, NoteMatiere] = Field(default_factory=dict)

    @field_validator('code')
    @classmethod
    def valider_code(cls, v):
        if not code_valide(v):
            raise ValueError(
                'Code : 3 lettres majuscules + 3 chiffres. Ex: AAD004'
            )
        return v

    @field_validator('numero')
    @classmethod
    def valider_numero(cls, v):
        if not numero_valide(v.upper()):
            raise ValueError(
                'Numéro : 7 caractères alphanumériques. Ex: H5G32YR'
            )
        return v.upper()

    @field_validator('nom')
    @classmethod
    def valider_nom(cls, v):
        return normaliser_nom(v)

    @field_validator('prenom')
    @classmethod
    def valider_prenom(cls, v):
        return normaliser_prenom(v)


class EtudiantModifier(BaseModel):
    """
    Modification partielle — tous les champs optionnels.
    """
    nom:            str | None  = Field(default=None, min_length=2)
    prenom:         str | None  = Field(default=None, min_length=3)
    date_naissance: date | None = None
    classe:         str | None  = None

    # Mêmes règles qu'à la création : une modification ne doit pas
    # permettre d'enregistrer ce que la création aurait refusé.
    @field_validator('nom')
    @classmethod
    def valider_nom(cls, v):
        return None if v is None else normaliser_nom(v)

    @field_validator('prenom')
    @classmethod
    def valider_prenom(cls, v):
        return None if v is None else normaliser_prenom(v)
