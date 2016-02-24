BEGIN;

--Remove aanvaarding begunstiging and custom clause voor Select+
DELETE FROM financial_item_clause WHERE id IN (272, 273, 278, 279);

--Alter names of beneficiary-clauses to something more descriptive
UPDATE financial_item_clause SET name = 'Mede-eigenaar(s)' WHERE id = 268;
UPDATE financial_item_clause SET name = 'Echgeno(o)t(e)/Partner' WHERE id = 269;
UPDATE financial_item_clause SET name = 'Kinderen' WHERE id = 270;
UPDATE financial_item_clause SET name = 'Ouders' WHERE id = 271;
UPDATE financial_item_clause SET name = 'Co-propriétaire(s)' WHERE id = 274;
UPDATE financial_item_clause SET name = 'Conjoint/Cohabitant légal' WHERE id = 275;
UPDATE financial_item_clause SET name = 'Enfants' WHERE id = 276;
UPDATE financial_item_clause SET name = 'Parents' WHERE id = 277;

COMMIT;
