BEGIN;
CREATE TABLE res_country (
	name VARCHAR(64) NOT NULL, 
	code VARCHAR(2) NOT NULL, 
	perm_id INTEGER, 
	create_uid INTEGER, 
	create_date DATETIME, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE geographic_boundary
(
  id serial NOT NULL,
  code character varying(10),
  name character varying(100) NOT NULL,
  row_type character varying(40),
  latitude numeric(6,4),
  longitude numeric(7,4),
  CONSTRAINT geographic_boundary_pkey PRIMARY KEY (id)
);
CREATE TABLE geographic_boundary_city
(
  geographicboundary_id integer NOT NULL,
  country_geographicboundary_id integer NOT NULL,
  CONSTRAINT geographic_boundary_city_pkey PRIMARY KEY (geographicboundary_id),
  CONSTRAINT geographic_boundary_city_country_geographicboundary_id_fk FOREIGN KEY (country_geographicboundary_id)
      REFERENCES geographic_boundary_country (geographicboundary_id) MATCH SIMPLE
      ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT geographic_boundary_city_geographicboundary_id_fkey FOREIGN KEY (geographicboundary_id)
      REFERENCES geographic_boundary (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE CASCADE
);
CREATE TABLE geographic_boundary_country
(
  geographicboundary_id integer NOT NULL,
  CONSTRAINT geographic_boundary_country_pkey PRIMARY KEY (geographicboundary_id),
  CONSTRAINT geographic_boundary_country_geographicboundary_id_fkey FOREIGN KEY (geographicboundary_id)
      REFERENCES geographic_boundary (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE CASCADE
);
CREATE TABLE financial_package (
	name VARCHAR(255) NOT NULL, 
	comment TEXT, 
	from_customer INTEGER NOT NULL, 
	thru_customer INTEGER NOT NULL, 
	from_supplier INTEGER NOT NULL, 
	thru_supplier INTEGER NOT NULL, 
	id INTEGER NOT NULL, code character varying(25), from_agreement character varying(15), 
	PRIMARY KEY (id)
);

CREATE TABLE batch_job_type (
	name VARCHAR(256) NOT NULL, 
	id INTEGER NOT NULL, 
	parent_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT batch_job_type_parent_id_fk FOREIGN KEY(parent_id) REFERENCES batch_job_type (id)
);

CREATE TABLE bank_klant (
	state VARCHAR(50), 
	venice_id INTEGER, 
	venice_nummer INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE res_partner_title (
	name VARCHAR(46) NOT NULL, 
	shortcut VARCHAR(16) NOT NULL, 
	domain VARCHAR(24) NOT NULL, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE hypo_afpunt_sessie (
	venice_tick_session_id INTEGER NOT NULL, 
	venice_active_year VARCHAR(14) NOT NULL, 
	venice_id INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE hypo_index_type (
	description VARCHAR(200), 
	name VARCHAR(25) NOT NULL, 
	url VARCHAR(255), 
	url_described_by INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE hypo_domiciliering (
	batch INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	mededeling1 VARCHAR(15), 
	referentie VARCHAR(10), 
	spildatum DATE NOT NULL, 
	datum_opmaak DATE NOT NULL, 
	export VARCHAR(100), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE bank_account (
	number VARCHAR(14) NOT NULL, 
	description VARCHAR(250) NOT NULL, 
	accounting_state INTEGER NOT NULL, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE party (
	row_type VARCHAR(40) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE financial_document_type (
	description VARCHAR(48) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE res_partner_function (
	name VARCHAR(64) NOT NULL, 
	code VARCHAR(8), 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE financial_security (
	name VARCHAR(255) NOT NULL, 
	account_number INTEGER, 
	account_infix VARCHAR(15), 
	isin VARCHAR(12), 
	bfi VARCHAR(12), 
	currency INTEGER NOT NULL, 
	comment TEXT, 
	sales_delay INTEGER NOT NULL, 
	purchase_delay INTEGER NOT NULL, 
	transfer_revenue_account VARCHAR(15), 
	order_lines_from DATE NOT NULL, 
	order_lines_thru DATE NOT NULL, 
	row_type VARCHAR(40) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE accounting_period (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	from_book_date DATE NOT NULL, 
	thru_book_date DATE NOT NULL, 
	from_doc_date DATE NOT NULL, 
	thru_doc_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);


CREATE TABLE authentication_mechanism (
	authentication_type INTEGER NOT NULL, 
	username VARCHAR(40) NOT NULL, 
	password VARCHAR(200), 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	last_login DATETIME, 
	representation TEXT, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);




CREATE TABLE hypo_rente_tabel_categorie (
	doel_aankoop_gebouw_registratie BOOLEAN, 
	doel_herfinanciering BOOLEAN, 
	doel_nieuwbouw BOOLEAN, 
	name VARCHAR(100) NOT NULL, 
	doel_centralisatie BOOLEAN, 
	doel_aankoop_terrein BOOLEAN, 
	doel_handelszaak BOOLEAN, 
	doel_aankoop_gebouw_btw BOOLEAN, 
	doel_overbrugging BOOLEAN, 
	doel_renovatie BOOLEAN, 
	doel_behoud BOOLEAN, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (doel_aankoop_gebouw_registratie IN (0, 1)), 
	CHECK (doel_herfinanciering IN (0, 1)), 
	CHECK (doel_nieuwbouw IN (0, 1)), 
	CHECK (doel_centralisatie IN (0, 1)), 
	CHECK (doel_aankoop_terrein IN (0, 1)), 
	CHECK (doel_handelszaak IN (0, 1)), 
	CHECK (doel_aankoop_gebouw_btw IN (0, 1)), 
	CHECK (doel_overbrugging IN (0, 1)), 
	CHECK (doel_renovatie IN (0, 1)), 
	CHECK (doel_behoud IN (0, 1))
);
CREATE TABLE financial_security_order (
	order_date DATE NOT NULL, 
	comment TEXT, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE insurance_mortality_rate_table (
	name VARCHAR(255) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE party_category (
	name VARCHAR(40) NOT NULL, 
	color VARCHAR(8), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE bank_constraint (
	object_name VARCHAR(40) NOT NULL, 
	object_id INTEGER NOT NULL, 
	constraint_id INTEGER NOT NULL, 
	message VARCHAR(100), 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);



CREATE TABLE fixture (
	model VARCHAR(255) NOT NULL, 
	primary_key INTEGER NOT NULL, 
	fixture_key VARCHAR(255) NOT NULL, 
	fixture_class VARCHAR(255), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);




CREATE TABLE hypo_bijkomende_waarborg (
	name VARCHAR(100) NOT NULL, 
	waarde NUMERIC(17, 2) NOT NULL, 
	type VARCHAR(50) NOT NULL, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE bank_postcodes (
	provincie VARCHAR(30) NOT NULL, 
	priority INTEGER, 
	gewest VARCHAR(30) NOT NULL, 
	postcode VARCHAR(10) NOT NULL, 
	gemeente VARCHAR(128) NOT NULL, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE kapbon_product_beschrijving (
	naam VARCHAR(100) NOT NULL, 
	standaard_commissie FLOAT, 
	minimum_serienummer INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);



CREATE TABLE translation (
	language VARCHAR(20) NOT NULL, 
	source VARCHAR(500) NOT NULL, 
	value VARCHAR(500), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);



CREATE TABLE bond_product_beschrijving (
	looptijd_maanden INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	coupure FLOAT NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE bank_settings (
	language VARCHAR(6),
	value VARCHAR(250) NOT NULL, 
	"key" VARCHAR(250) NOT NULL, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE geographic_boundary (
	code VARCHAR(10), 
	name VARCHAR(40) NOT NULL, 
	row_type VARCHAR(40) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE hypo_periode (
	startdatum DATE NOT NULL, 
	einddatum DATE NOT NULL, 
	state VARCHAR(50) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE authentication_group (
	name VARCHAR(256) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE hypo_betaling (
	line_number INTEGER NOT NULL, 
	open_amount NUMERIC(16, 2) NOT NULL, 
	ticked BOOLEAN NOT NULL, 
	datum DATE, 
	remark VARCHAR(256), 
	venice_active_year VARCHAR(10), 
	venice_doc INTEGER NOT NULL, 
	account VARCHAR(14) NOT NULL, 
	venice_book_type VARCHAR(10), 
	amount NUMERIC(16, 2), 
	book_date DATE NOT NULL, 
	creation_date DATE NOT NULL, 
	venice_id INTEGER, 
	venice_book VARCHAR(10) NOT NULL, 
	quantity NUMERIC(17, 6) NOT NULL, 
	value NUMERIC(17, 6), 
	text VARCHAR(25), 
	accounting_state INTEGER NOT NULL, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (ticked IN (0, 1)), 
	CONSTRAINT hypo_betaling_hypo_betaling_unique UNIQUE (book_date, venice_book, venice_doc, line_number)
);











CREATE TABLE fixture_version (
	fixture_version INTEGER NOT NULL, 
	fixture_class VARCHAR(255), 
	PRIMARY KEY (fixture_class)
);


CREATE TABLE financial_work_effort (
	type INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE financial_transaction (
	agreement_date DATE NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	code VARCHAR(15) NOT NULL, 
	text TEXT, 
	transaction_type INTEGER NOT NULL, 
	period_type INTEGER NOT NULL, 
	document VARCHAR(100), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);






CREATE TABLE party_address_role_type (
	code VARCHAR(10), 
	description VARCHAR(40), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE hypo_dossierkost_historiek (
	basis_bedrag NUMERIC(17, 2) NOT NULL, 
	basis_percentage NUMERIC(17, 2) NOT NULL, 
	start_datum DATE NOT NULL, 
	name VARCHAR(100), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE financial_product_index_applicability (
	described_by INTEGER NOT NULL, 
	apply_from_date DATE NOT NULL, 
	apply_thru_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	available_for_id INTEGER NOT NULL, 
	index_type_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_product_index_applicability_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_product (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_product_index_applicability_index_type_id_fk FOREIGN KEY(index_type_id) REFERENCES hypo_index_type (id) ON DELETE restrict ON UPDATE cascade
);





CREATE TABLE product_feature_applicability (
	premium_from_date DATE NOT NULL, 
	premium_thru_date DATE NOT NULL, 
	apply_from_date DATE NOT NULL, 
	apply_thru_date DATE NOT NULL, 
	value NUMERIC(17, 5) NOT NULL, 
	from_amount NUMERIC(17, 2) NOT NULL, 
	thru_amount NUMERIC(17, 2), 
	from_agreed_duration INTEGER NOT NULL, 
	thru_agreed_duration INTEGER NOT NULL, 
	from_passed_duration INTEGER NOT NULL, 
	thru_passed_duration INTEGER NOT NULL, 
	from_attributed_duration INTEGER NOT NULL, 
	thru_attributed_duration INTEGER NOT NULL, 
	automated_clearing BOOLEAN, 
	overrule_required BOOLEAN, 
	id INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	premium_period_type INTEGER, 
	comment TEXT, 
	available_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (automated_clearing IN (0, 1)), 
	CHECK (overrule_required IN (0, 1)), 
	CONSTRAINT product_feature_applicability_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_product (id) ON DELETE cascade ON UPDATE cascade
);





CREATE TABLE financial_notification_applicability (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	notification_type INTEGER NOT NULL, 
	template VARCHAR(500) NOT NULL, 
	language VARCHAR(10), 
	premium_period_type INTEGER, 
	id INTEGER NOT NULL, 
	available_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_notification_applicability_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_package (id) ON DELETE cascade ON UPDATE cascade
);




CREATE TABLE person (
	first_name VARCHAR(40) NOT NULL, 
	last_name VARCHAR(40) NOT NULL, 
	middle_name VARCHAR(40), 
	personal_title VARCHAR(10), 
	suffix VARCHAR(3), 
	sex VARCHAR(1), 
	birthdate DATE, 
	martial_status VARCHAR(1), 
	social_security_number VARCHAR(12), 
	passport_number VARCHAR(20), 
	passport_expiry_date DATE, 
	picture VARCHAR(100), 
	comment TEXT, 
	party_id INTEGER NOT NULL, 
	PRIMARY KEY (party_id), 
	FOREIGN KEY(party_id) REFERENCES party (id)
);
CREATE TABLE hypo_entry_presence (
	entry_id INTEGER NOT NULL, 
	venice_active_year VARCHAR(14) NOT NULL, 
	venice_id INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(entry_id) REFERENCES hypo_betaling (id)
);


CREATE TABLE financial_functional_setting_applicability (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	described_by INTEGER NOT NULL, 
	availability INTEGER NOT NULL, 
	comment TEXT, 
	id INTEGER NOT NULL, 
	available_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_functional_setting_applicability_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_package (id) ON DELETE cascade ON UPDATE cascade
);



CREATE TABLE bond_product (
	code INTEGER NOT NULL, 
	coupon_datum DATE NOT NULL, 
	start_datum DATE NOT NULL, 
	beschrijving INTEGER, 
	afsluit_datum DATE NOT NULL, 
	rente FLOAT NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT bond_product_beschrijving_fk FOREIGN KEY(beschrijving) REFERENCES bond_product_beschrijving (id)
);

CREATE TABLE kapbon_product_termijn_beschrijving (
	looptijd_maanden INTEGER, 
	product INTEGER, 
	volgorde INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT kapbon_product_termijn_beschrijving_product_fk FOREIGN KEY(product) REFERENCES kapbon_product_beschrijving (id)
);

CREATE TABLE financial_role_clause (
	described_by INTEGER NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	clause TEXT, 
	id INTEGER NOT NULL, 
	available_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_role_clause_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_package (id) ON DELETE cascade ON UPDATE cascade
);



CREATE TABLE financialtransaction_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES financial_transaction (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE insurance_mortality_rate_table_entry (
	year INTEGER NOT NULL, 
	l_x NUMERIC(17, 9) NOT NULL, 
	id INTEGER NOT NULL, 
	used_in_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT insurance_mortality_rate_table_entry_used_in_id_fk FOREIGN KEY(used_in_id) REFERENCES insurance_mortality_rate_table (id) ON DELETE cascade ON UPDATE cascade
);


CREATE TABLE financial_item_clause (
	name VARCHAR(255) NOT NULL, 
	clause TEXT, 
	language VARCHAR(10), 
	described_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	available_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_item_clause_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_package (id) ON DELETE cascade ON UPDATE cascade
);



CREATE TABLE kapbon_product_penalisatie (
	looptijd_maanden INTEGER, 
	product INTEGER, 
	penalisatie FLOAT NOT NULL, 
	volgorde INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT kapbon_product_penalisatie_product_fk FOREIGN KEY(product) REFERENCES kapbon_product_beschrijving (id)
);

CREATE TABLE authentication_group_member (
	authentication_group_id INTEGER NOT NULL, 
	authentication_mechanism_id INTEGER NOT NULL, 
	PRIMARY KEY (authentication_group_id, authentication_mechanism_id), 
	CONSTRAINT authentication_group_members_fk FOREIGN KEY(authentication_group_id) REFERENCES authentication_group (id), 
	CONSTRAINT authentication_group_members_inverse_fk FOREIGN KEY(authentication_mechanism_id) REFERENCES authentication_mechanism (id)
);
CREATE TABLE hypo_dossierkost_staffel (
	name VARCHAR(100), 
	minimum_ontleend_bedrag NUMERIC(17, 2) NOT NULL, 
	wijziging_percentage NUMERIC(17, 2) NOT NULL, 
	wijziging_bedrag NUMERIC(17, 2) NOT NULL, 
	historiek INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_dossierkost_staffel_historiek_fk FOREIGN KEY(historiek) REFERENCES hypo_dossierkost_historiek (id)
);

CREATE TABLE financial_security_quotation_period_type (
	quotation_period_type INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	financial_security_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_security_quotation_period_type_financial_security_id_fk FOREIGN KEY(financial_security_id) REFERENCES financial_security (id) ON DELETE cascade ON UPDATE cascade
);

CREATE TABLE kapbon_product (
	start_datum DATE, 
	beschrijving INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT kapbon_product_beschrijving_fk FOREIGN KEY(beschrijving) REFERENCES kapbon_product_beschrijving (id)
);

CREATE TABLE organization (
	name VARCHAR(50) NOT NULL, 
	logo VARCHAR(100), 
	tax_id VARCHAR(20), 
	party_id INTEGER NOT NULL, 
	PRIMARY KEY (party_id), 
	FOREIGN KEY(party_id) REFERENCES party (id)
);

CREATE TABLE financial_product_availability (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	available_for_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, availability integer, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_product_availability_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_package (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_product_availability_product_id_fk FOREIGN KEY(product_id) REFERENCES financial_product (id) ON DELETE restrict ON UPDATE cascade
);




CREATE TABLE financialsecurityorder_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES financial_security_order (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE financialworkeffort_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES financial_work_effort (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE financial_product_account (
	described_by INTEGER NOT NULL, 
	number VARCHAR(15) NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	available_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_product_account_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_product (id) ON DELETE cascade ON UPDATE cascade
);




CREATE TABLE financialsecurity_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES financial_security (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE hypo_index_historiek (
	from_date DATE NOT NULL, 
	value NUMERIC(17, 6) NOT NULL, 
	duration INTEGER, 
	type INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_index_historiek_type_fk FOREIGN KEY(type) REFERENCES hypo_index_type (id)
);

CREATE TABLE geographic_boundary_country (
	geographicboundary_id INTEGER NOT NULL, 
	PRIMARY KEY (geographicboundary_id), 
	FOREIGN KEY(geographicboundary_id) REFERENCES geographic_boundary (id)
);
CREATE TABLE insurance_coverage_availability (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	"of" INTEGER NOT NULL, 
	availability INTEGER NOT NULL, 
	reinsurance_rate NUMERIC(17, 2) NOT NULL, 
	id INTEGER NOT NULL, 
	available_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT insurance_coverage_availability_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_product (id) ON DELETE cascade ON UPDATE cascade
);





CREATE TABLE directdebitbatch_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES hypo_domiciliering (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE authentication_group_role (
	role_id INTEGER NOT NULL, 
	group_id INTEGER NOT NULL, 
	PRIMARY KEY (role_id, group_id), 
	FOREIGN KEY(group_id) REFERENCES authentication_group (id) ON DELETE cascade ON UPDATE cascade
);
CREATE TABLE batch_job (
	host VARCHAR(256) NOT NULL, 
	message TEXT, 
	id INTEGER NOT NULL, 
	type_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT batch_job_type_id_fk FOREIGN KEY(type_id) REFERENCES batch_job_type (id) ON DELETE restrict ON UPDATE cascade
);

CREATE TABLE financial_security_quotation (
	financial_security_id INTEGER NOT NULL, 
	purchase_date DATE NOT NULL, 
	sales_date DATE NOT NULL, 
	from_datetime DATETIME NOT NULL, 
	value NUMERIC(17, 6) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(financial_security_id) REFERENCES financial_security (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_security_quotation_financial_security_id_fk FOREIGN KEY(financial_security_id) REFERENCES financial_security (id)
);



CREATE TABLE party_category_party (
	party_category_id INTEGER NOT NULL, 
	party_id INTEGER NOT NULL, 
	PRIMARY KEY (party_category_id, party_id), 
	CONSTRAINT party_category_parties_fk FOREIGN KEY(party_category_id) REFERENCES party_category (id), 
	CONSTRAINT party_category_parties_inverse_fk FOREIGN KEY(party_id) REFERENCES party (id)
);
CREATE TABLE financial_product_fund_availability (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	default_target_percentage NUMERIC(17, 2) NOT NULL, 
	id INTEGER NOT NULL, 
	available_for_id INTEGER NOT NULL, 
	fund_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_product_fund_availability_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_product (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_product_fund_availability_fund_id_fk FOREIGN KEY(fund_id) REFERENCES financial_security (id) ON DELETE restrict ON UPDATE cascade
);




CREATE TABLE memento (
	model VARCHAR(256) NOT NULL, 
	primary_key INTEGER NOT NULL, 
	creation_date DATETIME, 
	memento_type INTEGER NOT NULL, 
	previous_attributes BLOB, 
	id INTEGER NOT NULL, 
	authentication_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT memento_authentication_id_fk FOREIGN KEY(authentication_id) REFERENCES authentication_mechanism (id) ON DELETE restrict ON UPDATE cascade
);




CREATE TABLE financial_account (
	id INTEGER NOT NULL, 
	package_id INTEGER NOT NULL, 
	text TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_account_package_id_fk FOREIGN KEY(package_id) REFERENCES financial_package (id) ON DELETE restrict ON UPDATE cascade
);

CREATE TABLE financial_security_feature (
	apply_from_date DATE NOT NULL, 
	apply_thru_date DATE NOT NULL, 
	value NUMERIC(17, 5) NOT NULL, 
	described_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	financial_security_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_security_feature_financial_security_id_fk FOREIGN KEY(financial_security_id) REFERENCES financial_security (id) ON DELETE cascade ON UPDATE cascade
);



CREATE TABLE financial_security_risk_assessment (
	financial_security_id INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	risk_type INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(financial_security_id) REFERENCES financial_security (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_security_risk_assessment_financial_security_id_fk FOREIGN KEY(financial_security_id) REFERENCES financial_security (id)
);

CREATE TABLE financial_transaction_credit_distribution (
	document VARCHAR(100), 
	iban VARCHAR(34) NOT NULL, 
	described_by INTEGER NOT NULL, 
	quantity NUMERIC(17, 6) NOT NULL, 
	id INTEGER NOT NULL, 
	financial_transaction_id INTEGER, 
	bank_identifier_code VARCHAR(11), 
	PRIMARY KEY (id), 
	CONSTRAINT financial_transaction_credit_distribution_financial_transaction_id_fk FOREIGN KEY(financial_transaction_id) REFERENCES financial_transaction (id) ON DELETE cascade ON UPDATE cascade
);



CREATE TABLE hypo_rente_tabel (
	looptijd INTEGER NOT NULL, 
	type_aflossing VARCHAR(50) NOT NULL, 
	categorie INTEGER NOT NULL, 
	name VARCHAR(100), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_rente_tabel_categorie_fk FOREIGN KEY(categorie) REFERENCES hypo_rente_tabel_categorie (id)
);

CREATE TABLE financial_fund (
	financialsecurity_id INTEGER NOT NULL, 
	PRIMARY KEY (financialsecurity_id), 
	FOREIGN KEY(financialsecurity_id) REFERENCES financial_security (id)
);
CREATE TABLE financialproduct_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES financial_product (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE financialaccount_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES financial_account (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE kapbon_product_rente (
	product INTEGER, 
	rente FLOAT NOT NULL, 
	beschrijving INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT kapbon_product_rente_product_fk FOREIGN KEY(product) REFERENCES kapbon_product (id), 
	CONSTRAINT kapbon_product_rente_beschrijving_fk FOREIGN KEY(beschrijving) REFERENCES kapbon_product_termijn_beschrijving (id)
);


CREATE TABLE hypo_rente_historiek (
	basis VARCHAR(7) NOT NULL, 
	tabel INTEGER NOT NULL, 
	start_datum DATE NOT NULL, 
	name VARCHAR(100), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_rente_historiek_tabel_fk FOREIGN KEY(tabel) REFERENCES hypo_rente_tabel (id)
);

CREATE TABLE financial_account_item (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	rank INTEGER NOT NULL, 
	use_custom_clause BOOLEAN NOT NULL, 
	custom_clause TEXT, 
	described_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	financial_account_id INTEGER NOT NULL, 
	associated_clause_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT check_account_associated_clause_or_custom_clause CHECK ((associated_clause_id IS NULL AND use_custom_clause = 't' AND custom_clause IS NOT NULL) OR (associated_clause_id > 0 AND use_custom_clause = 'f')), 
	CHECK (use_custom_clause IN (0, 1)), 
	CONSTRAINT financial_account_item_financial_account_id_fk FOREIGN KEY(financial_account_id) REFERENCES financial_account (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_account_item_associated_clause_id_fk FOREIGN KEY(associated_clause_id) REFERENCES financial_item_clause (id) ON DELETE restrict ON UPDATE cascade
);





CREATE TABLE bank_andere_ten_laste (
	persoon INTEGER, 
	lasthebber INTEGER, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT bank_andere_ten_laste_persoon_fk FOREIGN KEY(persoon) REFERENCES bank_natuurlijke_persoon (id), 
	CONSTRAINT bank_andere_ten_laste_lasthebber_fk FOREIGN KEY(lasthebber) REFERENCES bank_natuurlijke_persoon (id)
);
CREATE TABLE insurance_coverage_availability_mortality_rate_table (
	type INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	used_in_id INTEGER NOT NULL, 
	mortality_rate_table_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT insurance_coverage_availability_mortality_rate_table_used_in_id_fk FOREIGN KEY(used_in_id) REFERENCES insurance_coverage_availability (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT insurance_coverage_availability_mortality_rate_table_mortality_rate_table_id_fk FOREIGN KEY(mortality_rate_table_id) REFERENCES insurance_mortality_rate_table (id) ON DELETE cascade ON UPDATE cascade
);



CREATE TABLE insurance_coverage_level (
	type INTEGER NOT NULL, 
	coverage_limit_from NUMERIC(17, 2) NOT NULL, 
	coverage_limit_thru NUMERIC(17, 2) NOT NULL, 
	id INTEGER NOT NULL, 
	used_in_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT insurance_coverage_level_used_in_id_fk FOREIGN KEY(used_in_id) REFERENCES insurance_coverage_availability (id) ON DELETE cascade ON UPDATE cascade
);

CREATE TABLE bank_rechtspersoon (
	id INTEGER NOT NULL, 
	postcode VARCHAR(24), 
	vorm VARCHAR(50), 
	vertegenwoordiger INTEGER, 
	taal VARCHAR(50) NOT NULL, 
	email VARCHAR(64), 
	fax VARCHAR(64), 
	ondernemingsnummer VARCHAR(100) NOT NULL, 
	oprichtingsdatum DATE, 
	land INTEGER, 
	correspondentie_land INTEGER, 
	statuten VARCHAR(100), 
	juridische_vorm VARCHAR(50), 
	gemeente VARCHAR(128), 
	straat VARCHAR(128), 
	name VARCHAR(100) NOT NULL, 
	short_name VARCHAR(100), 
	activiteit VARCHAR(100), 
	gsm VARCHAR(64), 
	telefoon VARCHAR(64), 
	bestuurders VARCHAR(100), 
	origin VARCHAR(50), 
	tax_number VARCHAR(40), 
	perm_id INTEGER, 
	nota TEXT, 
	correspondentie_straat VARCHAR(128), 
	correspondentie_postcode VARCHAR(128), 
	correspondentie_gemeente VARCHAR(128),
	ownership_verified_at DATE, 
	PRIMARY KEY (id), 
	CONSTRAINT bank_rechtspersoon_vertegenwoordiger_fk FOREIGN KEY(vertegenwoordiger) REFERENCES bank_natuurlijke_persoon (id), 
	CONSTRAINT bank_rechtspersoon_land_fk FOREIGN KEY(land) REFERENCES res_country (id), 
	CONSTRAINT bank_rechtspersoon_correspondentie_land_fk FOREIGN KEY(correspondentie_land) REFERENCES res_country (id)
);
CREATE TABLE bank_kind_ten_laste (
	kind INTEGER, 
	lasthebber INTEGER, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT bank_kind_ten_laste_kind_fk FOREIGN KEY(kind) REFERENCES bank_natuurlijke_persoon (id), 
	CONSTRAINT bank_kind_ten_laste_lasthebber_fk FOREIGN KEY(lasthebber) REFERENCES bank_natuurlijke_persoon (id)
);
CREATE TABLE batchjob_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES batch_job (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE financial_product_feature_condition (
	described_by INTEGER NOT NULL, 
	value_from NUMERIC(17, 2) NOT NULL, 
	value_thru NUMERIC(17, 2) NOT NULL, 
	id INTEGER NOT NULL, 
	limit_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_product_feature_condition_limit_for_id_fk FOREIGN KEY(limit_for_id) REFERENCES product_feature_applicability (id) ON DELETE cascade ON UPDATE cascade
);

CREATE TABLE financial_account_functional_setting_application (
	described_by INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	clause TEXT, 
	id INTEGER NOT NULL, 
	applied_on_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_account_functional_setting_application_applied_on_id_fk FOREIGN KEY(applied_on_id) REFERENCES financial_account (id) ON DELETE restrict ON UPDATE cascade
);



CREATE TABLE financialsecurityquotation_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES financial_security_quotation (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE geographic_boundary_city (
	geographicboundary_id INTEGER NOT NULL, 
	country_geographicboundary_id INTEGER NOT NULL, 
	PRIMARY KEY (geographicboundary_id), 
	FOREIGN KEY(geographicboundary_id) REFERENCES geographic_boundary (id), 
	CONSTRAINT geographic_boundary_city_country_geographicboundary_id_fk FOREIGN KEY(country_geographicboundary_id) REFERENCES geographic_boundary_country (geographicboundary_id) ON DELETE cascade ON UPDATE cascade
);

CREATE TABLE financial_product_feature_distribution (
	recipient INTEGER NOT NULL, 
	distribution NUMERIC(17, 5) NOT NULL, 
	comment VARCHAR(256), 
	id INTEGER NOT NULL, 
	of_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_product_feature_distribution_of_id_fk FOREIGN KEY(of_id) REFERENCES product_feature_applicability (id) ON DELETE cascade ON UPDATE cascade
);

CREATE TABLE bond_owner (
	klant INTEGER, 
	bankrekening VARCHAR(16) NOT NULL, 
	"from" DATE, 
	thru DATE, 
	bond INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT bond_owner_klant_fk FOREIGN KEY(klant) REFERENCES bank_klant (id), 
	CONSTRAINT bond_owner_bond_fk FOREIGN KEY(bond) REFERENCES bond_product (id)
);


CREATE TABLE hypo_dossierkost_wijziging (
	voorwaarde VARCHAR(50), 
	name VARCHAR(100), 
	staffel_vermindering INTEGER, 
	staffel_vermeerdering INTEGER, 
	wijziging_percentage NUMERIC(17, 2) NOT NULL, 
	wijziging_bedrag NUMERIC(17, 2) NOT NULL, 
	x NUMERIC(17, 2), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_dossierkost_wijziging_staffel_vermindering_fk FOREIGN KEY(staffel_vermindering) REFERENCES hypo_dossierkost_staffel (id), 
	CONSTRAINT hypo_dossierkost_wijziging_staffel_vermeerdering_fk FOREIGN KEY(staffel_vermeerdering) REFERENCES hypo_dossierkost_staffel (id)
);


CREATE TABLE bank_economische_eigenaar (
	id INTEGER NOT NULL, 
	natuurlijke_persoon INTEGER, 
	rechtspersoon INTEGER, 
	rechtspersoon_waarvan_eigenaar INTEGER, 
	percentage_eigendom INTEGER, 
	perm_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT bank_economische_eigenaar_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id), 
	CONSTRAINT bank_economische_eigenaar_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT bank_economische_eigenaar_rechtspersoon_waarvan_eigenaar_fk FOREIGN KEY(rechtspersoon_waarvan_eigenaar) REFERENCES bank_rechtspersoon (id)
);
CREATE TABLE financial_security_role (
	number VARCHAR(20), 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	described_by INTEGER NOT NULL, 
	rechtspersoon INTEGER, 
	id INTEGER NOT NULL, 
	financial_security_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_security_role_financial_security_id_fk FOREIGN KEY(financial_security_id) REFERENCES financial_security (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_security_role_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id)
);




CREATE TABLE bank_bestuurder (
	id INTEGER NOT NULL, 
	natuurlijke_persoon INTEGER, 
	rechtspersoon INTEGER, 
	bestuurde_rechtspersoon INTEGER, 
	datum_mandaat DATE, 
	bruto_vergoeding FLOAT, 
	perm_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT bank_bestuurder_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id), 
	CONSTRAINT bank_bestuurder_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT bank_bestuurder_bestuurde_rechtspersoon_fk FOREIGN KEY(bestuurde_rechtspersoon) REFERENCES bank_rechtspersoon (id)
);
CREATE TABLE kapbon_bestelling (
	open_amount FLOAT, 
	temp_product INTEGER, 
	opmerking TEXT, 
	datum DATE NOT NULL, 
	temp_aan_toonder BOOLEAN, 
	venice_doc INTEGER, 
	datum_start_priv DATE, 
	korting FLOAT, 
	temp_coupure FLOAT, 
	venice_active_year VARCHAR(10), 
	state VARCHAR(50), 
	venice_book_type VARCHAR(10), 
	venice_book VARCHAR(10), 
	makelaar_id INTEGER, 
	bestelbon_nummer INTEGER, 
	afleveringstaks FLOAT, 
	temp_aantal INTEGER, 
	venice_id INTEGER, 
	administratiekosten FLOAT, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (temp_aan_toonder IN (0, 1)), 
	CONSTRAINT kapbon_bestelling_temp_product_fk FOREIGN KEY(temp_product) REFERENCES kapbon_product_beschrijving (id), 
	CONSTRAINT kapbon_bestelling_makelaar_id_fk FOREIGN KEY(makelaar_id) REFERENCES bank_rechtspersoon (id)
);


CREATE TABLE bank_bank_account (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	described_by INTEGER NOT NULL, 
	iban VARCHAR(34) NOT NULL, 
	id INTEGER NOT NULL, 
	rechtspersoon INTEGER, 
	natuurlijke_persoon INTEGER, 
	bank_identifier_code VARCHAR(11), 
	PRIMARY KEY (id), 
	FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade
);



CREATE TABLE financial_account_notification (
	id INTEGER NOT NULL, 
	date DATE NOT NULL, 
	balance NUMERIC(17, 2) NOT NULL, 
	message VARCHAR(100), 
	entry_book_date DATE NOT NULL, 
	entry_document INTEGER NOT NULL, 
	entry_book VARCHAR(25) NOT NULL, 
	entry_line_number INTEGER NOT NULL, 
	natuurlijke_persoon INTEGER, 
	rechtspersoon INTEGER, 
	generated_by_id INTEGER NOT NULL, 
	application_of_id INTEGER NOT NULL, 
	account_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_account_notification_persoon_fk CHECK (natuurlijke_persoon is not null or rechtspersoon is not null), 
	CONSTRAINT financial_account_notification_generated_by_id_fk FOREIGN KEY(generated_by_id) REFERENCES financial_work_effort (id), 
	CONSTRAINT financial_account_notification_application_of_id_fk FOREIGN KEY(application_of_id) REFERENCES financial_notification_applicability (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_account_notification_account_id_fk FOREIGN KEY(account_id) REFERENCES financial_account (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_account_notification_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_account_notification_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade
);








CREATE TABLE bond_bestelling (
	makelaar_id INTEGER, 
	open_amount FLOAT, 
	datum DATE NOT NULL, 
	state VARCHAR(50), 
	opmerking TEXT, 
	venice_active_year VARCHAR(10), 
	venice_doc INTEGER, 
	nummer INTEGER NOT NULL, 
	bankrekening VARCHAR(16) NOT NULL, 
	venice_book_type VARCHAR(10), 
	venice_id INTEGER, 
	venice_book VARCHAR(10), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT bond_bestelling_makelaar_id_fk FOREIGN KEY(makelaar_id) REFERENCES bank_rechtspersoon (id)
);

CREATE TABLE bank_supplier (
	id INTEGER NOT NULL, 
	rechtspersoon INTEGER, 
	natuurlijke_persoon INTEGER, 
	supplier_number INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT bank_supplier_persoon_fk CHECK (natuurlijke_persoon is not null or rechtspersoon is not null), 
	CONSTRAINT bank_supplier_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT bank_supplier_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade
);


CREATE TABLE bank_official_number (
	type INTEGER NOT NULL, 
	number VARCHAR(128) NOT NULL, 
	issue_date DATE, 
	note TEXT, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	rechtspersoon_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT bank_official_number_rechtspersoon_id_fk FOREIGN KEY(rechtspersoon_id) REFERENCES bank_rechtspersoon (id)
);



CREATE TABLE bank_commercial_relation (
	id INTEGER NOT NULL, 
	to_rechtspersoon INTEGER NOT NULL, 
	type INTEGER NOT NULL, 
	number VARCHAR(20), 
	rechtspersoon INTEGER, 
	natuurlijke_persoon INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(to_rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade
);



CREATE TABLE bank_jaarverslag_rechtspersoon (
	verslag VARCHAR(100), 
	rechtspersoon INTEGER, 
	datum DATE, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT bank_jaarverslag_rechtspersoon_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id)
);
CREATE TABLE bank_persoon (
	id INTEGER NOT NULL, 
	rechtspersoon INTEGER, 
	natuurlijke_persoon INTEGER, 
	perm_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT bank_persoon_persoon_fk CHECK (natuurlijke_persoon is not null or rechtspersoon is not null), 
	CONSTRAINT bank_persoon_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT bank_persoon_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade
);


CREATE TABLE kapcontract_onderschrijver (
	rechtspersoon INTEGER, 
	natuurlijke_persoon INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT kapcontract_onderschrijver_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT kapcontract_onderschrijver_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id)
);


CREATE TABLE address (
	street1 VARCHAR(128) NOT NULL, 
	street2 VARCHAR(128), 
	id INTEGER NOT NULL, 
	city_geographicboundary_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT address_city_geographicboundary_id_fk FOREIGN KEY(city_geographicboundary_id) REFERENCES geographic_boundary_city (geographicboundary_id) ON DELETE cascade ON UPDATE cascade
);

CREATE TABLE hypo_rente_wijziging (
	voorwaarde VARCHAR(50), 
	name VARCHAR(100), 
	historiek_id_vermindering INTEGER, 
	wijziging VARCHAR(7) NOT NULL, 
	x NUMERIC(17, 2), 
	historiek_id_vermeerdering INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_rente_wijziging_historiek_id_vermindering_fk FOREIGN KEY(historiek_id_vermindering) REFERENCES hypo_rente_historiek (id), 
	CONSTRAINT hypo_rente_wijziging_historiek_id_vermeerdering_fk FOREIGN KEY(historiek_id_vermeerdering) REFERENCES hypo_rente_historiek (id)
);


CREATE TABLE hypo_verzekering (
	polis VARCHAR(40), 
	amount NUMERIC(17, 2), 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	makelaar_id INTEGER, 
	maatschappij_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_verzekering_makelaar_id_fk FOREIGN KEY(makelaar_id) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT hypo_verzekering_maatschappij_id_fk FOREIGN KEY(maatschappij_id) REFERENCES bank_rechtspersoon (id)
);


CREATE TABLE financial_account_role (
	id INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	described_by INTEGER NOT NULL, 
	natuurlijke_persoon INTEGER, 
	rechtspersoon INTEGER, 
	rank INTEGER NOT NULL, 
	use_custom_clause BOOLEAN, 
	custom_clause TEXT, 
	surmortality NUMERIC(6, 2), 
	financial_account_id INTEGER NOT NULL, 
	associated_clause_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_account_role_persoon_fk CHECK (natuurlijke_persoon is not null or rechtspersoon is not null), 
	CHECK (use_custom_clause IN (0, 1)), 
	CONSTRAINT financial_account_role_financial_account_id_fk FOREIGN KEY(financial_account_id) REFERENCES financial_account (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_account_role_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_account_role_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_account_role_associated_clause_id_fk FOREIGN KEY(associated_clause_id) REFERENCES financial_role_clause (id) ON DELETE restrict ON UPDATE cascade
);





CREATE TABLE kapcontract_contract (
	intrest VARCHAR(10), 
	makelaar_id INTEGER, 
	afkoop_venice_doc INTEGER, 
	onderschrijver INTEGER NOT NULL, 
	afkoop_datum DATE, 
	start_datum DATE NOT NULL, 
	pand BOOLEAN, 
	afkoop_venice_id INTEGER, 
	dubbel BOOLEAN, 
	betalings_interval INTEGER NOT NULL, 
	nummer INTEGER NOT NULL, 
	premie FLOAT NOT NULL, 
	state VARCHAR(50), 
	reductie_datum DATE, 
	looptijd INTEGER NOT NULL, 
	agent_code VARCHAR(5), 
	kapitaal FLOAT NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (pand IN (0, 1)), 
	CHECK (dubbel IN (0, 1)), 
	CONSTRAINT kapcontract_contract_makelaar_id_fk FOREIGN KEY(makelaar_id) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT kapcontract_contract_onderschrijver_fk FOREIGN KEY(onderschrijver) REFERENCES kapcontract_onderschrijver (id)
);


CREATE TABLE kapbon_kapbon (
	controle_stuk_nummer VARCHAR(10), 
	pand BOOLEAN, 
	mathematisch_datum DATE, 
	afkoop_datum_aanvraag DATE, 
	bestelling INTEGER, 
	betaal_datum DATE, 
	in_bewaring BOOLEAN, 
	afkoop_datum DATE, 
	serie_nummer INTEGER, 
	afkoop_terug_te_betalen_korting FLOAT, 
	coupure FLOAT NOT NULL, 
	controle_watermerk BOOLEAN, 
	opmerking TEXT, 
	geen_controle_stuk_nummer BOOLEAN, 
	stuk_nummer VARCHAR(10), 
	aan_toonder BOOLEAN, 
	afkoop_gekapitaliseerd_bedrag FLOAT, 
	controle_handtekening BOOLEAN, 
	betaald FLOAT, 
	state VARCHAR(50), 
	afkoop_klant_nummer INTEGER, 
	product INTEGER NOT NULL, 
	gestolen_stuk_nummer VARCHAR(10), 
	controle_diefstal BOOLEAN, 
	kapbon_nummer_import VARCHAR(15), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (pand IN (0, 1)), 
	CHECK (in_bewaring IN (0, 1)), 
	CHECK (controle_watermerk IN (0, 1)), 
	CHECK (geen_controle_stuk_nummer IN (0, 1)), 
	CHECK (aan_toonder IN (0, 1)), 
	CHECK (controle_handtekening IN (0, 1)), 
	CHECK (controle_diefstal IN (0, 1)), 
	CONSTRAINT kapbon_kapbon_bestelling_fk FOREIGN KEY(bestelling) REFERENCES kapbon_bestelling (id), 
	CONSTRAINT kapbon_kapbon_product_fk FOREIGN KEY(product) REFERENCES kapbon_product_beschrijving (id)
);


CREATE TABLE bond_bestellijn (
	product INTEGER NOT NULL, 
	state VARCHAR(50), 
	aantal INTEGER NOT NULL, 
	verlopen_dagen_in_rekening BOOLEAN NOT NULL, 
	correctie_rente FLOAT NOT NULL, 
	bestelling INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (verlopen_dagen_in_rekening IN (0, 1)), 
	CONSTRAINT bond_bestellijn_product_fk FOREIGN KEY(product) REFERENCES bond_product (id), 
	CONSTRAINT bond_bestellijn_bestelling_fk FOREIGN KEY(bestelling) REFERENCES bond_bestelling (id)
);


CREATE TABLE hypo_te_hypothekeren_goed (
	verwerving VARCHAR(50), 
	venale_verkoopwaarde NUMERIC(17, 2), 
	postcode VARCHAR(10) NOT NULL, 
	huurwaarde NUMERIC(17, 2), 
	bestemming VARCHAR(50), 
	straat VARCHAR(100) NOT NULL, 
	type VARCHAR(50), 
	gemeente VARCHAR(30) NOT NULL, 
	compromis VARCHAR(100), 
	vrijwillige_verkoop NUMERIC(17, 2), 
	gedwongen_verkoop NUMERIC(17, 2), 
	brandverzekering INTEGER, 
	schattingsverslag VARCHAR(100), 
	kadaster VARCHAR(40), 
	bewoonbare_oppervlakte NUMERIC(5, 2), 
	straat_breedte_grond NUMERIC(5, 2), 
	straat_breedte_gevel NUMERIC(5, 2), 
	id INTEGER NOT NULL, 
	schatter_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_te_hypothekeren_goed_schatter_id_fk FOREIGN KEY(schatter_id) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT hypo_te_hypothekeren_goed_brandverzekering_fk FOREIGN KEY(brandverzekering) REFERENCES hypo_verzekering (id)
);


CREATE TABLE party_address (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	comment VARCHAR(256), 
	id INTEGER NOT NULL, 
	party_id INTEGER NOT NULL, 
	address_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT party_address_party_id_fk FOREIGN KEY(party_id) REFERENCES party (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT party_address_address_id_fk FOREIGN KEY(address_id) REFERENCES address (id) ON DELETE cascade ON UPDATE cascade
);




CREATE TABLE bond_bond (
	state VARCHAR(50), 
	opmerking TEXT, 
	bestelling INTEGER NOT NULL, 
	product INTEGER NOT NULL, 
	serie_nummer INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT bond_bond_bestelling_fk FOREIGN KEY(bestelling) REFERENCES bond_bestelling (id), 
	CONSTRAINT bond_bond_product_fk FOREIGN KEY(product) REFERENCES bond_product (id)
);


CREATE TABLE hypo_hypotheek (
	origin VARCHAR(50), 
	id INTEGER NOT NULL, 
	kosten_andere NUMERIC(17, 2), 
	kosten_bouwwerken NUMERIC(17, 2), 
	company_id INTEGER NOT NULL, 
	aanvraagnummer INTEGER NOT NULL, 
	rank INTEGER NOT NULL, 
	schattingskosten NUMERIC(17, 2), 
	domiciliering BOOLEAN, 
	ontvangen_voorschot NUMERIC(17, 2), 
	kosten_architect NUMERIC(17, 2), 
	aanvraagdocument VARCHAR(100), 
	kosten_btw NUMERIC(17, 2), 
	eigen_middelen NUMERIC(17, 2), 
	woonsparen BOOLEAN, 
	notariskosten_aankoop NUMERIC(17, 2), 
	domiciliering_rekening VARCHAR(15), 
	aankoopprijs NUMERIC(17, 2), 
	aktedatum DATE NOT NULL, 
	verzekeringskosten NUMERIC(17, 2), 
	wederbelegingsvergoeding NUMERIC(17, 2), 
	temp_copy_from INTEGER, 
	achterstal_rekening VARCHAR(4), 
	kosten_verzekering NUMERIC(17, 2), 
	achterstal NUMERIC(17, 2), 
	state VARCHAR(15), 
	handlichting NUMERIC(17, 2), 
	notariskosten_hypotheek NUMERIC(17, 2), 
	correctie_levensonderhoud NUMERIC(17, 2), 
	wettelijk_kader VARCHAR(15), 
	aanvraagdatum DATE NOT NULL, 
	bijkomende_informatie TEXT, 
	broker_agent_id INTEGER, 
	broker_relation_id INTEGER, 
	PRIMARY KEY (id), 
	UNIQUE (company_id, aanvraagnummer, rank), 
	CHECK (domiciliering IN (0, 1)), 
	CHECK (woonsparen IN (0, 1)), 
	FOREIGN KEY(broker_agent_id) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(broker_relation_id) REFERENCES bank_commercial_relation (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_hypotheek_temp_copy_from_fk FOREIGN KEY(temp_copy_from) REFERENCES hypo_hypotheek (id)
);



CREATE TABLE financial_account_notification_acceptance (
	document VARCHAR(100), 
	reception_date DATE NOT NULL, 
	post_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	acceptance_of_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_account_notification_acceptance_acceptance_of_id_fk FOREIGN KEY(acceptance_of_id) REFERENCES financial_account_notification (id) ON DELETE restrict ON UPDATE cascade
);



CREATE TABLE bank_persoon_klant_rel (
	primary_contact BOOLEAN, 
	persoon INTEGER, 
	klant INTEGER, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (primary_contact IN (0, 1)), 
	CONSTRAINT bank_persoon_klant_rel_persoon_fk FOREIGN KEY(persoon) REFERENCES bank_persoon (id), 
	CONSTRAINT bank_persoon_klant_rel_klant_fk FOREIGN KEY(klant) REFERENCES bank_klant (id)
);


CREATE TABLE kapbon_koper (
	rechtspersoon INTEGER, 
	bestelling INTEGER, 
	natuurlijke_persoon INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT kapbon_koper_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT kapbon_koper_bestelling_fk FOREIGN KEY(bestelling) REFERENCES kapbon_bestelling (id), 
	CONSTRAINT kapbon_koper_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id)
);



CREATE TABLE financial_account_broker (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	financial_account_id INTEGER NOT NULL, 
	broker_relation_id INTEGER, 
	broker_agent_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_account_broker_financial_account_id_fk FOREIGN KEY(financial_account_id) REFERENCES financial_account (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_account_broker_broker_relation_id_fk FOREIGN KEY(broker_relation_id) REFERENCES bank_commercial_relation (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_account_broker_broker_agent_id_fk FOREIGN KEY(broker_agent_id) REFERENCES bank_rechtspersoon (id)
);





CREATE TABLE bond_subscriber (
	rechtspersoon INTEGER, 
	natuurlijke_persoon INTEGER, 
	bestelling INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT bond_subscriber_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT bond_subscriber_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id), 
	CONSTRAINT bond_subscriber_bestelling_fk FOREIGN KEY(bestelling) REFERENCES bond_bestelling (id)
);



CREATE TABLE financial_broker_availability (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	available_for_id INTEGER NOT NULL, 
	broker_relation_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_broker_availability_available_for_id_fk FOREIGN KEY(available_for_id) REFERENCES financial_package (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_broker_availability_broker_relation_id_fk FOREIGN KEY(broker_relation_id) REFERENCES bank_commercial_relation (id) ON DELETE restrict ON UPDATE cascade
);




CREATE TABLE financialagreement_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES financial_agreement (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE "financial_agreement_premium_schedule" (
	financial_agreement_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	duration INTEGER NOT NULL, 
	payment_duration INTEGER, 
	period_type INTEGER NOT NULL, 
	amount NUMERIC(17, 2) NOT NULL, 
	increase_rate NUMERIC(17, 5) NOT NULL, 
	direct_debit BOOLEAN NOT NULL, 
	id INTEGER NOT NULL, insured_duration INTEGER, coverage_amortization_id INTEGER, insured_from_date DATE, coverage_for_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(financial_agreement_id) REFERENCES financial_agreement (id) ON DELETE cascade ON UPDATE cascade, 
	FOREIGN KEY(product_id) REFERENCES financial_product (id) ON DELETE restrict ON UPDATE cascade, 
	CHECK (direct_debit IN (0, 1))
);

CREATE TABLE financial_agreement_item (
	rank INTEGER NOT NULL, 
	use_custom_clause BOOLEAN NOT NULL, 
	custom_clause TEXT, 
	described_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	financial_agreement_id INTEGER NOT NULL, 
	associated_clause_id INTEGER, 
	PRIMARY KEY (id), 
	CHECK (use_custom_clause IN (0, 1)), 
	CONSTRAINT financial_agreement_item_financial_agreement_id_fk FOREIGN KEY(financial_agreement_id) REFERENCES financial_agreement (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_agreement_item_associated_clause_id_fk FOREIGN KEY(associated_clause_id) REFERENCES financial_item_clause (id) ON DELETE restrict ON UPDATE cascade
);



CREATE TABLE hypo_beslissing (
	goedgekeurde_dossierkosten NUMERIC(17, 2), 
	datum DATE, 
	opmerkingen TEXT, 
	datum_voorwaarde DATE, 
	beslissingsdocument VARCHAR(100), 
	state VARCHAR(50) NOT NULL, 
	hypotheek INTEGER NOT NULL, 
	correctie_dossierkosten NUMERIC(17, 2), 
	id INTEGER NOT NULL, financial_agreement_id integer, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_beslissing_hypotheek_fk FOREIGN KEY(hypotheek) REFERENCES hypo_hypotheek (id)
);

CREATE TABLE hypo_goed (
	verwerving VARCHAR(50), 
	venale_verkoopwaarde NUMERIC(17, 2), 
	postcode VARCHAR(10) NOT NULL, 
	huurwaarde NUMERIC(17, 2), 
	bestemming VARCHAR(50), 
	straat VARCHAR(100) NOT NULL, 
	type VARCHAR(50), 
	gemeente VARCHAR(30) NOT NULL, 
	hypotheek_id INTEGER, 
	id INTEGER NOT NULL, financial_agrement_id integer, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_goed_hypotheek_id_fk FOREIGN KEY(hypotheek_id) REFERENCES hypo_hypotheek (id)
);

CREATE TABLE financial_agreement_role (
	id INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	rank INTEGER NOT NULL, 
	use_custom_clause BOOLEAN, 
	custom_clause TEXT, 
	surmortality NUMERIC(6, 2), 
	rechtspersoon INTEGER, 
	natuurlijke_persoon INTEGER, 
	financial_agreement_id INTEGER NOT NULL, 
	associated_clause_id INTEGER, reference varchar(30), 
	PRIMARY KEY (id), 
	CONSTRAINT financial_agreement_role_persoon_fk CHECK (natuurlijke_persoon is not null or rechtspersoon is not null), 
	CHECK (use_custom_clause IN (0, 1)), 
	FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_agreement_role_financial_agreement_id_fk FOREIGN KEY(financial_agreement_id) REFERENCES financial_agreement (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_agreement_role_associated_clause_id_fk FOREIGN KEY(associated_clause_id) REFERENCES financial_role_clause (id) ON DELETE restrict ON UPDATE cascade
);





CREATE TABLE hypo_application_role (
	id INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	rank INTEGER NOT NULL, 
	thru_date DATE NOT NULL, 
	rechtspersoon INTEGER, 
	natuurlijke_persoon INTEGER, 
	application_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_application_role_persoon_fk CHECK (natuurlijke_persoon is not null or rechtspersoon is not null), 
	FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_application_role_application_id_fk FOREIGN KEY(application_id) REFERENCES hypo_hypotheek (id)
);




CREATE TABLE kapcontract_begunstigde (
	rechtspersoon INTEGER, 
	contract INTEGER, 
	natuurlijke_persoon INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT kapcontract_begunstigde_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT kapcontract_begunstigde_contract_fk FOREIGN KEY(contract) REFERENCES kapcontract_contract (id), 
	CONSTRAINT kapcontract_begunstigde_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id)
);



CREATE TABLE financial_agreement_functional_setting_agreement (
	described_by INTEGER NOT NULL, 
	clause TEXT, 
	id INTEGER NOT NULL, 
	agreed_on_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_agreement_functional_setting_agreement_agreed_on_id_fk FOREIGN KEY(agreed_on_id) REFERENCES financial_agreement (id) ON DELETE cascade ON UPDATE cascade
);

CREATE TABLE kapbon_afkoop_document (
	venice_doc INTEGER, 
	kapbon INTEGER NOT NULL, 
	open_amount FLOAT, 
	datum DATE NOT NULL, 
	venice_id INTEGER, 
	state VARCHAR(50), 
	venice_book_type VARCHAR(10), 
	venice_active_year VARCHAR(10), 
	venice_book VARCHAR(10), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT kapbon_afkoop_document_kapbon_fk FOREIGN KEY(kapbon) REFERENCES kapbon_kapbon (id)
);

CREATE TABLE financial_agreement_asset_usage (
	id INTEGER NOT NULL, 
	financial_agreement_id INTEGER NOT NULL, 
	asset_usage_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_agreement_asset_usage_financial_agreement_id_fk FOREIGN KEY(financial_agreement_id) REFERENCES financial_agreement (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_agreement_asset_usage_asset_usage_id_fk FOREIGN KEY(asset_usage_id) REFERENCES hypo_te_hypothekeren_goed (id) ON DELETE restrict ON UPDATE cascade
);


CREATE TABLE hypo_bedrag (
	type_vervaldag VARCHAR(50), 
	doel_nieuwbouw BOOLEAN, 
	doel_herfinanciering BOOLEAN, 
	opname_periode INTEGER, 
	doel_handelszaak BOOLEAN, 
	doel_aankoop_terrein BOOLEAN, 
	terugbetaling_start INTEGER, 
	bedrag NUMERIC(17, 2) NOT NULL, 
	doel_renovatie BOOLEAN, 
	doel_behoud BOOLEAN, 
	doel_aankoop_gebouw_btw BOOLEAN, 
	doel_aankoop_gebouw_registratie BOOLEAN, 
	doel_centralisatie BOOLEAN, 
	doel_overbrugging BOOLEAN, 
	terugbetaling_interval INTEGER, 
	looptijd INTEGER NOT NULL, 
	opname_schijven INTEGER, 
	type_aflossing VARCHAR(50) NOT NULL, 
	hypotheek_id INTEGER, 
	id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, financial_agreement_id INTEGER, 
	PRIMARY KEY (id), 
	CHECK (doel_nieuwbouw IN (0, 1)), 
	CHECK (doel_herfinanciering IN (0, 1)), 
	CHECK (doel_handelszaak IN (0, 1)), 
	CHECK (doel_aankoop_terrein IN (0, 1)), 
	CHECK (doel_renovatie IN (0, 1)), 
	CHECK (doel_behoud IN (0, 1)), 
	CHECK (doel_aankoop_gebouw_btw IN (0, 1)), 
	CHECK (doel_aankoop_gebouw_registratie IN (0, 1)), 
	CHECK (doel_centralisatie IN (0, 1)), 
	CHECK (doel_overbrugging IN (0, 1)), 
	CONSTRAINT hypo_bedrag_product_id_fk FOREIGN KEY(product_id) REFERENCES financial_product (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_bedrag_hypotheek_id_fk FOREIGN KEY(hypotheek_id) REFERENCES hypo_hypotheek (id)
);


CREATE TABLE contact_mechanism (
	mechanism VARCHAR(256) NOT NULL, 
	id INTEGER NOT NULL, 
	party_address_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT contact_mechanism_party_address_id_fk FOREIGN KEY(party_address_id) REFERENCES party_address (id) ON DELETE set null ON UPDATE cascade
);

CREATE TABLE financial_clearing_mandate (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	iban VARCHAR(34) NOT NULL, 
	identification VARCHAR(35) NOT NULL, 
	date DATE NOT NULL, 
	document VARCHAR(100), 
	described_by INTEGER NOT NULL, 
	sequence_type INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	bank_identifier_code VARCHAR(11), 
	financial_agreement_id INTEGER, 
	financial_account_id INTEGER, 
	hypotheek_id INTEGER, 
	modification_of_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_clearing_mandate_financial_agreement_id_fk FOREIGN KEY(financial_agreement_id) REFERENCES financial_agreement (id) ON DELETE set null ON UPDATE cascade, 
	CONSTRAINT financial_clearing_mandate_financial_account_id_fk FOREIGN KEY(financial_account_id) REFERENCES financial_account (id) ON DELETE set null ON UPDATE cascade, 
	CONSTRAINT financial_clearing_mandate_hypotheek_id_fk FOREIGN KEY(hypotheek_id) REFERENCES hypo_hypotheek (id) ON DELETE set null ON UPDATE cascade, 
	CONSTRAINT financial_clearing_mandate_modification_of_id_fk FOREIGN KEY(modification_of_id) REFERENCES financial_clearing_mandate (id) ON DELETE restrict ON UPDATE cascade
);





CREATE TABLE financial_account_asset_usage (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	financial_account_id INTEGER NOT NULL, 
	asset_usage_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_account_asset_usage_financial_account_id_fk FOREIGN KEY(financial_account_id) REFERENCES financial_account (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_account_asset_usage_asset_usage_id_fk FOREIGN KEY(asset_usage_id) REFERENCES hypo_te_hypothekeren_goed (id) ON DELETE restrict ON UPDATE cascade
);




CREATE TABLE hypo_lopend_krediet (
	status INTEGER NOT NULL, 
	ontleend_bedrag NUMERIC(17, 2), 
	saldo NUMERIC(17, 2), 
	krediet_nummer VARCHAR(40), 
	einddatum DATE, 
	maandlast NUMERIC(17, 2), 
	regelmatig_betaald BOOLEAN, 
	hypotheek INTEGER, 
	datum_akte DATE, 
	looptijd INTEGER, 
	rentevoet NUMERIC(6, 4), 
	type_aflossing VARCHAR(50) NOT NULL, 
	verkocht BOOLEAN, 
	datum_verkoop DATE, 
	prijs_goed NUMERIC(10, 2), 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	maatschappij_id INTEGER, 
	PRIMARY KEY (id), 
	CHECK (regelmatig_betaald IN (0, 1)), 
	CHECK (verkocht IN (0, 1)), 
	CONSTRAINT hypo_lopend_krediet_maatschappij_id_fk FOREIGN KEY(maatschappij_id) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT hypo_lopend_krediet_hypotheek_fk FOREIGN KEY(hypotheek) REFERENCES hypo_hypotheek (id)
);


CREATE TABLE financial_document (
	document_date DATE NOT NULL, 
	document VARCHAR(100), 
	description VARCHAR(200), 
	summary TEXT, 
	id INTEGER NOT NULL, 
	type_id INTEGER NOT NULL, 
	financial_agreement_id INTEGER, 
	financial_account_id INTEGER, 
	financial_transaction_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_document_type_id_fk FOREIGN KEY(type_id) REFERENCES financial_document_type (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_document_financial_agreement_id_fk FOREIGN KEY(financial_agreement_id) REFERENCES financial_agreement (id) ON DELETE set null ON UPDATE cascade, 
	CONSTRAINT financial_document_financial_account_id_fk FOREIGN KEY(financial_account_id) REFERENCES financial_account (id) ON DELETE set null ON UPDATE cascade, 
	CONSTRAINT financial_document_financial_transaction_id_fk FOREIGN KEY(financial_transaction_id) REFERENCES financial_transaction (id) ON DELETE set null ON UPDATE cascade
);





CREATE TABLE kapbon_afkoper (
	rechtspersoon INTEGER, 
	kapbon INTEGER, 
	natuurlijke_persoon INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT kapbon_afkoper_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT kapbon_afkoper_kapbon_fk FOREIGN KEY(kapbon) REFERENCES kapbon_kapbon (id), 
	CONSTRAINT kapbon_afkoper_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id)
);



CREATE TABLE financialaccountnotificationacceptance_status (
	status_datetime DATE, 
	status_from_date DATE, 
	status_thru_date DATE, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	classified_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	status_for_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(status_for_id) REFERENCES financial_account_notification_acceptance (id) ON DELETE cascade ON UPDATE cascade
);







CREATE TABLE hypo_bijkomende_waarborg_hypotheek (
	bijkomende_waarborg INTEGER NOT NULL, 
	hypotheek INTEGER, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, financial_agreement_id integer, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_bijkomende_waarborg_hypotheek_bijkomende_waarborg_fk FOREIGN KEY(bijkomende_waarborg) REFERENCES hypo_bijkomende_waarborg (id), 
	CONSTRAINT hypo_bijkomende_waarborg_hypotheek_hypotheek_fk FOREIGN KEY(hypotheek) REFERENCES hypo_hypotheek (id)
);


CREATE TABLE hypo_application_functional_setting_agreement (
	described_by INTEGER NOT NULL, 
	clause TEXT, 
	id INTEGER NOT NULL, 
	agreed_on_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_application_functional_setting_agreement_agreed_on_id_fk FOREIGN KEY(agreed_on_id) REFERENCES hypo_hypotheek (id) ON DELETE restrict ON UPDATE cascade
);

CREATE TABLE hypo_application_role_feature (
	value NUMERIC(17, 5) NOT NULL, 
	described_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	of_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(of_id) REFERENCES hypo_application_role (id) ON DELETE cascade ON UPDATE cascade
);
CREATE TABLE hypo_goedgekeurd_bedrag (
	goedgekeurde_referentie_index VARCHAR(7), 
	goedgekeurd_type_vervaldag VARCHAR(50), 
	beslissing INTEGER, 
	voorgestelde_maximale_conjunctuur_ristorno VARCHAR(7), 
	voorgestelde_maximale_spaar_ristorno VARCHAR(7), 
	goedgekeurde_minimale_afwijking VARCHAR(7), 
	voorgestelde_reserveringsprovisie VARCHAR(12), 
	voorgestelde_eerste_herziening_ristorno INTEGER, 
	bedrag INTEGER NOT NULL, 
	goedgekeurde_maximale_conjunctuur_ristorno VARCHAR(7), 
	goedgekeurd_terugbetaling_interval INTEGER, 
	goedgekeurde_rente VARCHAR(12), 
	goedgekeurde_eerste_herziening_ristorno INTEGER, 
	voorgestelde_maximale_product_ristorno VARCHAR(7), 
	goedgekeurde_maximale_stijging VARCHAR(7), 
	voorgestelde_maximale_daling VARCHAR(7), 
	voorgestelde_volgende_herzieningen_ristorno INTEGER, 
	state VARCHAR(50) NOT NULL, 
	goedgekeurde_maximale_product_ristorno VARCHAR(7), 
	goedgekeurde_looptijd INTEGER, 
	goedgekeurde_opname_periode INTEGER, 
	voorgestelde_minimale_afwijking VARCHAR(7), 
	goedgekeurde_maximale_spaar_ristorno VARCHAR(7), 
	goedgekeurde_eerste_herziening INTEGER, 
	type VARCHAR(50) NOT NULL, 
	goedgekeurde_maximale_daling VARCHAR(7), 
	commerciele_wijziging VARCHAR(7), 
	venice_doc INTEGER, 
	wijziging INTEGER, 
	voorgestelde_referentie_index VARCHAR(7), 
	goedgekeurd_bedrag NUMERIC(17, 2), 
	goedgekeurde_intrest_b VARCHAR(12), 
	voorgesteld_index_type INTEGER, 
	voorgestelde_eerste_herziening INTEGER, 
	goedgekeurde_intrest_a VARCHAR(12), 
	goedgekeurd_terugbetaling_start INTEGER, 
	goedgekeurde_reserverings_provisie VARCHAR(12), 
	goedgekeurde_opname_schijven INTEGER, 
	goedgekeurd_type_aflossing VARCHAR(50), 
	voorgestelde_volgende_herzieningen INTEGER, 
	goedgekeurde_volgende_herzieningen INTEGER, 
	voorgestelde_maximale_stijging VARCHAR(7), 
	goedgekeurde_jaarrente VARCHAR(12), 
	goedgekeurde_volgende_herzieningen_ristorno INTEGER, 
	venice_id INTEGER, 
	goedgekeurd_index_type INTEGER, 
	goedgekeurd_vast_bedrag NUMERIC(17, 2), 
	id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_goedgekeurd_bedrag_product_id_fk FOREIGN KEY(product_id) REFERENCES financial_product (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_goedgekeurd_bedrag_beslissing_fk FOREIGN KEY(beslissing) REFERENCES hypo_beslissing (id), 
	CONSTRAINT hypo_goedgekeurd_bedrag_bedrag_fk FOREIGN KEY(bedrag) REFERENCES hypo_bedrag (id), 
	CONSTRAINT hypo_goedgekeurd_bedrag_voorgesteld_index_type_fk FOREIGN KEY(voorgesteld_index_type) REFERENCES hypo_index_type (id), 
	CONSTRAINT hypo_goedgekeurd_bedrag_goedgekeurd_index_type_fk FOREIGN KEY(goedgekeurd_index_type) REFERENCES hypo_index_type (id)
);






CREATE TABLE hypo_eigenaar_goed (
	id INTEGER NOT NULL, 
	rechtspersoon INTEGER, 
	goed_id INTEGER, 
	natuurlijke_persoon INTEGER, 
	te_hypothekeren_goed_id INTEGER, 
	percentage NUMERIC(17, 2), 
	type VARCHAR(50), 
	perm_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_eigenaar_goed_persoon_fk CHECK (natuurlijke_persoon is not null or rechtspersoon is not null), 
	CONSTRAINT hypo_eigenaar_goed_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_eigenaar_goed_goed_id_fk FOREIGN KEY(goed_id) REFERENCES hypo_goed (id), 
	CONSTRAINT hypo_eigenaar_goed_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_eigenaar_goed_te_hypothekeren_goed_id_fk FOREIGN KEY(te_hypothekeren_goed_id) REFERENCES hypo_te_hypothekeren_goed (id)
);




CREATE TABLE hypo_waarborg (
	goed_id INTEGER, 
	saldo NUMERIC(17, 2), 
	te_hypothekeren_goed_id INTEGER, 
	bedrag NUMERIC(17, 2), 
	aanhorigheden NUMERIC(17, 2), 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	instelling_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_waarborg_goed_id_fk FOREIGN KEY(goed_id) REFERENCES hypo_goed (id), 
	CONSTRAINT hypo_waarborg_instelling_id_fk FOREIGN KEY(instelling_id) REFERENCES bank_rechtspersoon (id), 
	CONSTRAINT hypo_waarborg_te_hypothekeren_goed_id_fk FOREIGN KEY(te_hypothekeren_goed_id) REFERENCES hypo_te_hypothekeren_goed (id)
);



CREATE TABLE bank_direct_debit_item (
	part_of_id INTEGER NOT NULL, 
	sequence_type INTEGER NOT NULL, 
	item_description VARCHAR(140) NOT NULL, 
	request_at DATE NOT NULL, 
	status INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	mandated_by_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(part_of_id) REFERENCES hypo_domiciliering (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT bank_direct_debit_item_mandated_by_id_fk FOREIGN KEY(mandated_by_id) REFERENCES financial_clearing_mandate (id) ON DELETE restrict ON UPDATE cascade
);

CREATE TABLE hypo_ontlener_lopend_krediet (
	id INTEGER NOT NULL, 
	rechtspersoon INTEGER, 
	natuurlijke_persoon INTEGER, 
	lopend_krediet INTEGER, 
	perm_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_ontlener_lopend_krediet_persoon_fk CHECK (natuurlijke_persoon is not null or rechtspersoon is not null), 
	CONSTRAINT hypo_ontlener_lopend_krediet_rechtspersoon_fk FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_ontlener_lopend_krediet_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_ontlener_lopend_krediet_lopend_krediet_fk FOREIGN KEY(lopend_krediet) REFERENCES hypo_lopend_krediet (id)
);



CREATE TABLE financial_account_premium_schedule (
	id INTEGER NOT NULL, 
	financial_account_id INTEGER NOT NULL, 
	product_id INTEGER NOT NULL, 
	agreed_schedule_id INTEGER NOT NULL, 
	account_number INTEGER NOT NULL, 
	valid_from_date DATE NOT NULL, 
	valid_thru_date DATE NOT NULL, 
	payment_thru_date DATE NOT NULL, 
	premium_amount NUMERIC(17, 2) NOT NULL, 
	period_type INTEGER NOT NULL, 
	increase_rate NUMERIC(17, 5) NOT NULL, 
	direct_debit BOOLEAN NOT NULL, 
	version_id INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	history_of_id INTEGER NOT NULL, coverage_amortization_id INTEGER, insured_from_date DATE, insured_thru_date DATE, coverage_for_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(financial_account_id) REFERENCES financial_account (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(product_id) REFERENCES financial_product (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(agreed_schedule_id) REFERENCES time_deposit_invested_amount (id) ON DELETE restrict ON UPDATE cascade, 
	CHECK (direct_debit IN (0, 1)), 
	FOREIGN KEY(history_of_id) REFERENCES financial_account_premium_schedule (id) ON DELETE restrict ON UPDATE cascade
);








CREATE TABLE hypo_akte (
	beslissing INTEGER, 
	samenvatting VARCHAR(100), 
	juridische_goedkeuring VARCHAR(100), 
	datum_verlijden DATE, 
	datum_grossen DATE, 
	venice_id INTEGER, 
	venice_doc INTEGER, 
	state VARCHAR(50), 
	hypothecaire_rente NUMERIC(5, 4), 
	kantoor VARCHAR(30), 
	boek VARCHAR(15), 
	nummer VARCHAR(15), 
	rang INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_akte_beslissing_fk FOREIGN KEY(beslissing) REFERENCES hypo_beslissing (id)
);

CREATE TABLE hypo_aanvaarding (
	beslissing INTEGER NOT NULL, 
	datum_verstuurd DATE, 
	state VARCHAR(50) NOT NULL, 
	aanvaardingsbrief VARCHAR(100), 
	datum_ontvangst DATE, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_aanvaarding_beslissing_fk FOREIGN KEY(beslissing) REFERENCES hypo_beslissing (id)
);

CREATE TABLE hypo_application_feature_agreement (
	agreed_on_id INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	value NUMERIC(17, 5) NOT NULL, 
	comment TEXT, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(agreed_on_id) REFERENCES hypo_bedrag (id) ON DELETE cascade ON UPDATE cascade
);
CREATE TABLE financial_agreement_premium_feature (
	premium_from_date DATE NOT NULL, 
	premium_thru_date DATE NOT NULL, 
	apply_from_date DATE NOT NULL, 
	apply_thru_date DATE NOT NULL, 
	value NUMERIC(17, 5) NOT NULL, 
	from_amount NUMERIC(17, 2) NOT NULL, 
	thru_amount NUMERIC(17, 2), 
	from_agreed_duration INTEGER NOT NULL, 
	thru_agreed_duration INTEGER NOT NULL, 
	from_passed_duration INTEGER NOT NULL, 
	thru_passed_duration INTEGER NOT NULL, 
	from_attributed_duration INTEGER NOT NULL, 
	thru_attributed_duration INTEGER NOT NULL, 
	automated_clearing BOOLEAN, 
	overrule_required BOOLEAN, 
	id INTEGER NOT NULL, 
	agreed_on_id INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	premium_period_type INTEGER, 
	comment TEXT, 
	PRIMARY KEY (id), 
	CHECK (automated_clearing IN (0, 1)), 
	CHECK (overrule_required IN (0, 1)), 
	FOREIGN KEY(agreed_on_id) REFERENCES time_deposit_invested_amount (id) ON DELETE cascade ON UPDATE cascade
);





CREATE TABLE party_contact_mechanism (
	from_date DATE NOT NULL, 
	thru_date DATE, 
	comment VARCHAR(256), 
	id INTEGER NOT NULL, 
	party_id INTEGER NOT NULL, 
	contact_mechanism_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT party_contact_mechanism_party_id_fk FOREIGN KEY(party_id) REFERENCES party (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT party_contact_mechanism_contact_mechanism_id_fk FOREIGN KEY(contact_mechanism_id) REFERENCES contact_mechanism (id) ON DELETE cascade ON UPDATE cascade
);




CREATE TABLE financial_agreement_commission_distribution (
	described_by INTEGER NOT NULL, 
	recipient INTEGER NOT NULL, 
	distribution NUMERIC(17, 5) NOT NULL, 
	comment VARCHAR(256), 
	id INTEGER NOT NULL, 
	premium_schedule_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_agreement_commission_distribution_premium_schedule_id_fk FOREIGN KEY(premium_schedule_id) REFERENCES time_deposit_invested_amount (id) ON DELETE cascade ON UPDATE cascade
);

CREATE TABLE hypo_nodige_schuldsaldo (
	beslissing INTEGER, 
	natuurlijke_persoon INTEGER NOT NULL, 
	dekkingsgraad_schuldsaldo INTEGER, 
	schuldsaldo_voorzien BOOLEAN, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (schuldsaldo_voorzien IN (0, 1)), 
	CONSTRAINT hypo_nodige_schuldsaldo_beslissing_fk FOREIGN KEY(beslissing) REFERENCES hypo_beslissing (id), 
	CONSTRAINT hypo_nodige_schuldsaldo_natuurlijke_persoon_fk FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id)
);


CREATE TABLE financial_agreement_fund_distribution (
	target_percentage NUMERIC(17, 6) NOT NULL, 
	id INTEGER NOT NULL, 
	distribution_of_id INTEGER NOT NULL, 
	fund_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_agreement_fund_distribution_distribution_of_id_fk FOREIGN KEY(distribution_of_id) REFERENCES time_deposit_invested_amount (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_agreement_fund_distribution_fund_id_fk FOREIGN KEY(fund_id) REFERENCES financial_security (id) ON DELETE restrict ON UPDATE cascade
);


CREATE TABLE financial_account_fund_distribution (
	distribution_of_id INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	fund_id INTEGER NOT NULL, 
	target_percentage NUMERIC(17, 6) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(distribution_of_id) REFERENCES financial_account_premium_schedule (id) ON DELETE cascade ON UPDATE cascade, 
	FOREIGN KEY(fund_id) REFERENCES financial_security (id) ON DELETE restrict ON UPDATE cascade
);




CREATE TABLE insurance_insured_loan (
	loan_amount NUMERIC(17, 2), 
	interest_rate NUMERIC(10, 5), 
	number_of_months INTEGER, 
	type_of_payments INTEGER, 
	payment_interval INTEGER, 
	starting_date DATE, 
	id INTEGER NOT NULL, 
	loan_id INTEGER, 
	credit_institution_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT insurance_insured_loan_loan_id_fk FOREIGN KEY(loan_id) REFERENCES hypo_goedgekeurd_bedrag (id) ON DELETE restrict ON UPDATE restrict, 
	CONSTRAINT insurance_insured_loan_credit_institution_id_fk FOREIGN KEY(credit_institution_id) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE restrict
);


CREATE TABLE financial_account_commission_distribution (
	premium_schedule_id INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	recipient INTEGER NOT NULL, 
	distribution NUMERIC(17, 5) NOT NULL, 
	comment VARCHAR(256), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(premium_schedule_id) REFERENCES financial_account_premium_schedule (id) ON DELETE cascade ON UPDATE cascade
);
CREATE TABLE hypo_akte_aanvraag (
	percentage INTEGER NOT NULL, 
	akte INTEGER, 
	hypotheek INTEGER, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_akte_aanvraag_akte_fk FOREIGN KEY(akte) REFERENCES hypo_akte (id), 
	CONSTRAINT hypo_akte_aanvraag_hypotheek_fk FOREIGN KEY(hypotheek) REFERENCES hypo_hypotheek (id)
);


CREATE TABLE hypo_dossier (
	origin VARCHAR(15), 
	domiciliering BOOLEAN, 
	originele_startdatum DATE NOT NULL, 
	kredietcentrale_update DATE, 
	startdatum DATE NOT NULL, 
	goedgekeurd_bedrag INTEGER NOT NULL, 
	aanvraag INTEGER, 
	rappel_datum DATE, 
	einddatum DATE, 
	state VARCHAR(50), 
	maatschappij INTEGER, 
	kredietcentrale_gesignaleerd BOOLEAN, 
	nummer INTEGER NOT NULL, 
	company_id INTEGER NOT NULL, 
	rank INTEGER NOT NULL, 
	rappel_level INTEGER, 
	id INTEGER NOT NULL, 
	text TEXT, financial_agreement_id integer, 
	PRIMARY KEY (id), 
	UNIQUE (company_id, nummer, rank), 
	CHECK (domiciliering IN (0, 1)), 
	CHECK (kredietcentrale_gesignaleerd IN (0, 1)), 
	CONSTRAINT hypo_dossier_goedgekeurd_bedrag_fk FOREIGN KEY(goedgekeurd_bedrag) REFERENCES hypo_goedgekeurd_bedrag (id), 
	CONSTRAINT hypo_dossier_aanvraag_fk FOREIGN KEY(aanvraag) REFERENCES hypo_hypotheek (id)
);


CREATE TABLE hypo_handlichting (
	akte INTEGER NOT NULL, 
	datum_verlijden DATE NOT NULL, 
	bedrag NUMERIC(17, 2) NOT NULL, 
	document VARCHAR(100), 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_handlichting_akte_fk FOREIGN KEY(akte) REFERENCES hypo_akte (id)
);

CREATE TABLE financial_transaction_premium_schedule (
	within_id INTEGER NOT NULL, 
	premium_schedule_id INTEGER NOT NULL, 
	previous_version_id INTEGER NOT NULL, 
	next_version_id INTEGER, 
	described_by INTEGER NOT NULL, 
	quantity NUMERIC(17, 6) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(within_id) REFERENCES financial_transaction (id) ON DELETE cascade ON UPDATE cascade, 
	FOREIGN KEY(premium_schedule_id) REFERENCES financial_account_premium_schedule (id) ON DELETE restrict ON UPDATE cascade
);

CREATE TABLE financial_account_premium_feature (
	premium_from_date DATE NOT NULL, 
	premium_thru_date DATE NOT NULL, 
	apply_from_date DATE NOT NULL, 
	apply_thru_date DATE NOT NULL, 
	value NUMERIC(17, 5) NOT NULL, 
	from_amount NUMERIC(17, 2) NOT NULL, 
	thru_amount NUMERIC(17, 2), 
	from_agreed_duration INTEGER NOT NULL, 
	thru_agreed_duration INTEGER NOT NULL, 
	from_passed_duration INTEGER NOT NULL, 
	thru_passed_duration INTEGER NOT NULL, 
	from_attributed_duration INTEGER NOT NULL, 
	thru_attributed_duration INTEGER NOT NULL, 
	automated_clearing BOOLEAN, 
	overrule_required BOOLEAN, 
	id INTEGER NOT NULL, 
	applied_on_id INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	premium_period_type INTEGER, 
	comment TEXT, 
	PRIMARY KEY (id), 
	CHECK (automated_clearing IN (0, 1)), 
	CHECK (overrule_required IN (0, 1)), 
	FOREIGN KEY(applied_on_id) REFERENCES financial_account_premium_schedule (id) ON DELETE restrict ON UPDATE cascade
);





CREATE TABLE financial_security_order_line (
	id INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	quantity NUMERIC(17, 6) NOT NULL, 
	document_date DATE NOT NULL, 
	fulfillment_type INTEGER NOT NULL, 
	premium_schedule_id INTEGER NOT NULL, 
	part_of_id INTEGER, 
	financial_security_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(premium_schedule_id) REFERENCES financial_account_premium_schedule (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_security_order_line_part_of_id_fk FOREIGN KEY(part_of_id) REFERENCES financial_security_order (id) ON DELETE set null ON UPDATE cascade, 
	CONSTRAINT financial_security_order_line_financial_security_id_fk FOREIGN KEY(financial_security_id) REFERENCES financial_security (id) ON DELETE restrict ON UPDATE cascade
);





CREATE TABLE insurance_insured_loan_account (
	loan_amount NUMERIC(17, 2), 
	interest_rate NUMERIC(10, 5), 
	number_of_months INTEGER, 
	type_of_payments INTEGER, 
	payment_interval INTEGER, 
	starting_date DATE, 
	id INTEGER NOT NULL, 
	loan_id INTEGER, 
	credit_institution_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT insurance_insured_loan_account_loan_id_fk FOREIGN KEY(loan_id) REFERENCES hypo_goedgekeurd_bedrag (id) ON DELETE restrict ON UPDATE restrict, 
	CONSTRAINT insurance_insured_loan_account_credit_institution_id_fk FOREIGN KEY(credit_institution_id) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE restrict
);


CREATE TABLE hypo_wijziging (
	origin VARCHAR(50), 
	nieuwe_eerste_herziening_ristorno INTEGER, 
	nieuw_terugbetaling_start INTEGER, 
	datum_wijziging DATE NOT NULL, 
	open_amount NUMERIC(17, 2), 
	datum DATE NOT NULL, 
	nieuwe_rente VARCHAR(12), 
	nieuw_type_aflossing VARCHAR(50), 
	nieuw_bedrag NUMERIC(17, 2), 
	nieuwe_volgende_herzieningen INTEGER, 
	nieuwe_maximale_daling VARCHAR(7), 
	huidige_status VARCHAR(50), 
	nieuwe_opname_schijven INTEGER, 
	nieuwe_opname_periode INTEGER, 
	dossier INTEGER NOT NULL, 
	nieuwe_reserverings_provisie VARCHAR(12), 
	nieuwe_looptijd INTEGER, 
	nieuwe_eerste_herziening INTEGER, 
	nieuw_vast_bedrag NUMERIC(17, 2), 
	nieuwe_volgende_herzieningen_ristorno INTEGER, 
	wederbeleggingsvergoeding NUMERIC(17, 2), 
	nieuwe_status VARCHAR(50), 
	state VARCHAR(50), 
	nieuwe_maximale_product_ristorno VARCHAR(7), 
	opmerking TEXT, 
	nieuwe_maximale_stijging VARCHAR(7), 
	vorige_startdatum DATE, 
	nieuwe_jaarrente VARCHAR(12), 
	nieuwe_maximale_conjunctuur_ristorno VARCHAR(7), 
	vorig_goedgekeurd_bedrag INTEGER, 
	nieuwe_maximale_spaar_ristorno VARCHAR(7), 
	euribor VARCHAR(12), 
	nieuwe_minimale_afwijking VARCHAR(7), 
	nieuwe_referentie_index VARCHAR(7), 
	nieuwe_intrest_a VARCHAR(12), 
	nieuwe_intrest_b VARCHAR(12), 
	venice_book_type VARCHAR(10), 
	venice_book VARCHAR(10), 
	venice_id INTEGER, 
	venice_active_year VARCHAR(10), 
	venice_doc INTEGER, 
	goedgekeurd_index_type INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_wijziging_dossier_fk FOREIGN KEY(dossier) REFERENCES hypo_dossier (id), 
	CONSTRAINT hypo_wijziging_vorig_goedgekeurd_bedrag_fk FOREIGN KEY(vorig_goedgekeurd_bedrag) REFERENCES hypo_goedgekeurd_bedrag (id), 
	CONSTRAINT hypo_wijziging_goedgekeurd_index_type_fk FOREIGN KEY(goedgekeurd_index_type) REFERENCES hypo_index_type (id)
);



CREATE TABLE hypo_dossier_feature_application (
	described_by INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	comment TEXT, 
	id INTEGER NOT NULL, 
	applied_on_id INTEGER NOT NULL, 
	value NUMERIC(17, 5) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_dossier_feature_application_applied_on_id_fk FOREIGN KEY(applied_on_id) REFERENCES hypo_dossier (id) ON DELETE restrict ON UPDATE cascade
);



CREATE TABLE insurance_agreement_coverage (
	coverage_limit NUMERIC(17, 2) NOT NULL, 
	duration INTEGER NOT NULL, 
	from_date DATE, 
	id INTEGER NOT NULL, 
	premium_id INTEGER NOT NULL, 
	coverage_for_id INTEGER NOT NULL, 
	coverage_amortization_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT insurance_agreement_coverage_premium_id_fk FOREIGN KEY(premium_id) REFERENCES time_deposit_invested_amount (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT insurance_agreement_coverage_coverage_for_id_fk FOREIGN KEY(coverage_for_id) REFERENCES insurance_coverage_level (id) ON DELETE restrict ON UPDATE restrict, 
	CONSTRAINT insurance_agreement_coverage_coverage_amortization_id_fk FOREIGN KEY(coverage_amortization_id) REFERENCES insurance_insured_loan (id)
);




CREATE TABLE financial_transaction_premium_feature (
	premium_from_date DATE NOT NULL, 
	premium_thru_date DATE NOT NULL, 
	apply_from_date DATE NOT NULL, 
	apply_thru_date DATE NOT NULL, 
	value NUMERIC(17, 5) NOT NULL, 
	from_amount NUMERIC(17, 2) NOT NULL, 
	thru_amount NUMERIC(17, 2), 
	from_agreed_duration INTEGER NOT NULL, 
	thru_agreed_duration INTEGER NOT NULL, 
	from_passed_duration INTEGER NOT NULL, 
	thru_passed_duration INTEGER NOT NULL, 
	from_attributed_duration INTEGER NOT NULL, 
	thru_attributed_duration INTEGER NOT NULL, 
	automated_clearing BOOLEAN, 
	overrule_required BOOLEAN, 
	id INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	premium_period_type INTEGER, 
	comment TEXT, 
	applied_on_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (automated_clearing IN (0, 1)), 
	CHECK (overrule_required IN (0, 1)), 
	CONSTRAINT financial_transaction_premium_feature_applied_on_id_fk FOREIGN KEY(applied_on_id) REFERENCES financial_transaction_premium_schedule (id) ON DELETE restrict ON UPDATE cascade
);





CREATE TABLE hypo_dekking (
	dossier INTEGER, 
	valid_date_start DATE NOT NULL, 
	type VARCHAR(50) NOT NULL, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_dekking_dossier_fk FOREIGN KEY(dossier) REFERENCES hypo_dossier (id)
);

CREATE TABLE hypo_dossier_role (
	id INTEGER NOT NULL, 
	described_by INTEGER NOT NULL, 
	rank INTEGER NOT NULL, 
	thru_date DATE NOT NULL, 
	from_date DATE NOT NULL, 
	rechtspersoon INTEGER, 
	natuurlijke_persoon INTEGER, 
	dossier_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_dossier_role_persoon_fk CHECK (natuurlijke_persoon is not null or rechtspersoon is not null), 
	FOREIGN KEY(rechtspersoon) REFERENCES bank_rechtspersoon (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(natuurlijke_persoon) REFERENCES bank_natuurlijke_persoon (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_dossier_role_dossier_id_fk FOREIGN KEY(dossier_id) REFERENCES hypo_dossier (id) ON DELETE cascade ON UPDATE cascade
);




CREATE TABLE financial_transaction_premium_schedule_task (
	described_by INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	creating_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT financial_transaction_premium_schedule_task_creating_id_fk FOREIGN KEY(creating_id) REFERENCES financial_transaction_premium_schedule (id) ON DELETE cascade ON UPDATE cascade
);


CREATE TABLE bank_invoice_item (
	item_description VARCHAR(250) NOT NULL, 
	origin VARCHAR(50), 
	amount NUMERIC(17, 2) NOT NULL, 
	doc_date DATE NOT NULL, 
	dossier_id INTEGER, 
	status INTEGER NOT NULL, 
	row_type VARCHAR(40) NOT NULL, 
	id INTEGER NOT NULL, 
	modifier_of_id INTEGER, 
	related_to_id INTEGER, 
	premium_schedule_id INTEGER, 
	kosten_rappelbrieven NUMERIC(17, 2) NOT NULL, 
	rappel_level INTEGER, 
	afpunt_datum DATE, 
	te_betalen NUMERIC(17, 2) NOT NULL, 
	intrest_a NUMERIC(17, 2) NOT NULL, 
	intrest_b NUMERIC(17, 2) NOT NULL, 
	opmerking VARCHAR(50), 
	nummer INTEGER, 
	openstaand_kapitaal NUMERIC(17, 2) NOT NULL, 
	kapitaal NUMERIC(17, 2) NOT NULL, 
	gefactureerd NUMERIC(17, 2) NOT NULL, 
	geprovisioneerd NUMERIC(17, 2) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT invoice_item_schedule CHECK (dossier_id is not null or premium_schedule_id is not null), 
	FOREIGN KEY(modifier_of_id) REFERENCES bank_invoice_item (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(related_to_id) REFERENCES bank_invoice_item (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(premium_schedule_id) REFERENCES financial_account_premium_schedule (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT bank_invoice_item_dossier_id_fk FOREIGN KEY(dossier_id) REFERENCES hypo_dossier (id)
);




CREATE TABLE hypo_akte_dossier (
	dossier INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	akte INTEGER NOT NULL, 
	thru_date DATE NOT NULL, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_akte_dossier_dossier_fk FOREIGN KEY(dossier) REFERENCES hypo_dossier (id), 
	CONSTRAINT hypo_akte_dossier_akte_fk FOREIGN KEY(akte) REFERENCES hypo_akte (id)
);


CREATE TABLE hypo_melding_nbb (
	datum_betaling DATE, 
	comment VARCHAR(250), 
	state VARCHAR(50) NOT NULL, 
	bedrag NUMERIC(17, 2), 
	registratienummer VARCHAR(25), 
	eenheidnummer VARCHAR(50), 
	dossier INTEGER NOT NULL, 
	kredietnemer INTEGER, 
	type VARCHAR(50) NOT NULL, 
	datum_melding DATE, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_melding_nbb_dossier_fk FOREIGN KEY(dossier) REFERENCES hypo_dossier (id), 
	CONSTRAINT hypo_melding_nbb_kredietnemer_fk FOREIGN KEY(kredietnemer) REFERENCES bank_natuurlijke_persoon (id)
);


CREATE TABLE insurance_account_coverage (
	premium_id INTEGER NOT NULL, 
	coverage_limit NUMERIC(17, 2) NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	coverage_for_id INTEGER NOT NULL, 
	coverage_amortization_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(premium_id) REFERENCES financial_account_premium_schedule (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT insurance_account_coverage_coverage_for_id_fk FOREIGN KEY(coverage_for_id) REFERENCES insurance_coverage_level (id) ON DELETE restrict ON UPDATE restrict, 
	CONSTRAINT insurance_account_coverage_coverage_amortization_id_fk FOREIGN KEY(coverage_amortization_id) REFERENCES insurance_insured_loan_account (id)
);




CREATE TABLE hypo_korting (
	comment VARCHAR(250), 
	valid_date_start DATE NOT NULL, 
	rente NUMERIC(17, 6) NOT NULL, 
	dossier INTEGER, 
	type VARCHAR(50) NOT NULL, 
	datum DATE NOT NULL, 
	valid_date_end DATE NOT NULL, 
	origin VARCHAR(50), 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_korting_dossier_fk FOREIGN KEY(dossier) REFERENCES hypo_dossier (id)
);

CREATE TABLE hypo_dossier_functional_setting_application (
	described_by INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	clause TEXT, 
	id INTEGER NOT NULL, 
	applied_on_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_dossier_functional_setting_application_applied_on_id_fk FOREIGN KEY(applied_on_id) REFERENCES hypo_dossier (id) ON DELETE restrict ON UPDATE cascade
);



CREATE TABLE hypo_terugbetaling (
	onbetaalde_rente NUMERIC(17, 2), 
	openstaande_betalingen NUMERIC(17, 2), 
	nalatigheidsintresten_a NUMERIC(17, 2), 
	open_amount NUMERIC(17, 2), 
	datum DATE NOT NULL, 
	nalatigheidsintresten_b NUMERIC(17, 2), 
	rappelkosten NUMERIC(17, 2), 
	dagrente_correctie NUMERIC(17, 2), 
	wederbeleggingsvergoeding NUMERIC(17, 2), 
	state VARCHAR(50), 
	schadevergoeding_uitwinning NUMERIC(17, 2), 
	venice_book_type VARCHAR(10), 
	venice_book VARCHAR(10), 
	gerechtskosten NUMERIC(17, 2), 
	venice_doc INTEGER, 
	datum_terugbetaling DATE NOT NULL, 
	venice_active_year VARCHAR(10), 
	datum_stopzetting DATE, 
	openstaand_kapitaal NUMERIC(17, 2), 
	euribor NUMERIC(17, 5), 
	dossier INTEGER NOT NULL, 
	dagrente_percentage VARCHAR(12), 
	datum_laatst_betaalde_vervaldag DATE, 
	venice_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_terugbetaling_dossier_fk FOREIGN KEY(dossier) REFERENCES hypo_dossier (id)
);

CREATE TABLE hypo_bijkomende_waarborg_dossier (
	dossier INTEGER NOT NULL, 
	from_date DATE NOT NULL, 
	bijkomende_waarborg INTEGER NOT NULL, 
	thru_date DATE NOT NULL, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_bijkomende_waarborg_dossier_dossier_fk FOREIGN KEY(dossier) REFERENCES hypo_dossier (id), 
	CONSTRAINT hypo_bijkomende_waarborg_dossier_bijkomende_waarborg_fk FOREIGN KEY(bijkomende_waarborg) REFERENCES hypo_bijkomende_waarborg (id)
);


CREATE TABLE financial_transaction_fund_distribution (
	target_percentage NUMERIC(17, 6) NOT NULL, 
	change_target_percentage BOOLEAN NOT NULL, 
	new_target_percentage NUMERIC(17, 6) NOT NULL, 
	id INTEGER NOT NULL, 
	distribution_of_id INTEGER NOT NULL, 
	fund_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CHECK (change_target_percentage IN (0, 1)), 
	CONSTRAINT financial_transaction_fund_distribution_distribution_of_id_fk FOREIGN KEY(distribution_of_id) REFERENCES financial_transaction_premium_schedule (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT financial_transaction_fund_distribution_fund_id_fk FOREIGN KEY(fund_id) REFERENCES financial_security (id) ON DELETE restrict ON UPDATE cascade
);


CREATE TABLE hypo_dossier_direct_debit_mandate (
	hypo_dossier_id INTEGER NOT NULL, 
	financial_clearing_mandate_id INTEGER NOT NULL, 
	PRIMARY KEY (hypo_dossier_id, financial_clearing_mandate_id), 
	CONSTRAINT hypo_dossier_direct_debit_mandates_fk FOREIGN KEY(hypo_dossier_id) REFERENCES hypo_dossier (id), 
	CONSTRAINT hypo_dossier_direct_debit_mandates_inverse_fk FOREIGN KEY(financial_clearing_mandate_id) REFERENCES financial_clearing_mandate (id)
);
CREATE TABLE hypo_factuur (
	administratiekost NUMERIC(17, 2), 
	dossier INTEGER, 
	datum DATE NOT NULL, 
	state VARCHAR(50), 
	beschrijving VARCHAR(120) NOT NULL, 
	bedrag NUMERIC(17, 2) NOT NULL, 
	perm_id INTEGER, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_factuur_dossier_fk FOREIGN KEY(dossier) REFERENCES hypo_dossier (id)
);

CREATE TABLE hypo_dossier_broker (
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	dossier_id INTEGER NOT NULL, 
	broker_relation_id INTEGER, 
	broker_agent_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT hypo_dossier_broker_dossier_id_fk FOREIGN KEY(dossier_id) REFERENCES hypo_dossier (id) ON DELETE cascade ON UPDATE cascade, 
	CONSTRAINT hypo_dossier_broker_broker_relation_id_fk FOREIGN KEY(broker_relation_id) REFERENCES bank_commercial_relation (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_dossier_broker_broker_agent_id_fk FOREIGN KEY(broker_agent_id) REFERENCES bank_rechtspersoon (id)
);





CREATE TABLE hypo_loan_schedule_fulfillment (
	entry_book_date DATE NOT NULL, 
	entry_document INTEGER NOT NULL, 
	entry_book VARCHAR(25) NOT NULL, 
	entry_line_number INTEGER NOT NULL, 
	fulfillment_type INTEGER, 
	amount_distribution NUMERIC(17, 2) NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	id INTEGER NOT NULL, 
	booking_of_id INTEGER, 
	of_id INTEGER NOT NULL, 
	within_id INTEGER, 
	associated_to_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(booking_of_id) REFERENCES bank_invoice_item (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_loan_schedule_fulfillment_of_id_fk FOREIGN KEY(of_id) REFERENCES hypo_goedgekeurd_bedrag (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_loan_schedule_fulfillment_within_id_fk FOREIGN KEY(within_id) REFERENCES hypo_wijziging (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT hypo_loan_schedule_fulfillment_associated_to_id_fk FOREIGN KEY(associated_to_id) REFERENCES hypo_loan_schedule_fulfillment (id)
);










CREATE TABLE financial_account_premium_fulfillment (
	entry_book_date DATE NOT NULL, 
	entry_document INTEGER NOT NULL, 
	entry_book VARCHAR(25) NOT NULL, 
	entry_line_number INTEGER NOT NULL, 
	fulfillment_type INTEGER, 
	amount_distribution NUMERIC(17, 2) NOT NULL, 
	from_date DATE NOT NULL, 
	thru_date DATE NOT NULL, 
	of_id INTEGER NOT NULL, 
	id INTEGER NOT NULL, 
	booking_of_id INTEGER, 
	within_id INTEGER, 
	associated_to_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(of_id) REFERENCES financial_account_premium_schedule (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(booking_of_id) REFERENCES bank_invoice_item (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_account_premium_fulfillment_within_id_fk FOREIGN KEY(within_id) REFERENCES financial_transaction_premium_schedule (id) ON DELETE restrict ON UPDATE cascade, 
	CONSTRAINT financial_account_premium_fulfillment_associated_to_id_fk FOREIGN KEY(associated_to_id) REFERENCES financial_account_premium_fulfillment (id)
);









CREATE TABLE bank_direct_debit_invoice (
	of_id INTEGER NOT NULL, 
	via_id INTEGER NOT NULL, 
	amount NUMERIC(17, 2) NOT NULL, 
	id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(of_id) REFERENCES bank_invoice_item (id) ON DELETE restrict ON UPDATE cascade, 
	FOREIGN KEY(via_id) REFERENCES bank_direct_debit_item (id) ON DELETE restrict ON UPDATE cascade
);
CREATE TABLE [financial_product] ([row_type] VARCHAR (40) NOT NULL, [origin] VARCHAR (30), [jurisdiction] INTEGER, [account_number_prefix] INTEGER NOT NULL, [account_number_digits] INTEGER NOT NULL, [company_number_digits] INTEGER NOT NULL, [rank_number_digits] INTEGER NOT NULL, [name] VARCHAR (255) NOT NULL, [code] VARCHAR (100), [from_date] DATE NOT NULL, [book_from_date] DATE NOT NULL, [sales_discontinuation_date] DATE, [support_discontinuation_date] DATE, [accounting_year_transfer_book] VARCHAR (25), [external_application_book] VARCHAR (25), [supplier_distribution_book] VARCHAR (25), [comment] TEXT, [id] INTEGER NOT NULL, [specialization_of_id] INTEGER, [fund_number_digits] INTEGER, [financed_commissions_prefix] VARCHAR (15), [risk_sales_book] VARCHAR (25), [redemption_book] VARCHAR (25), [switch_book] VARCHAR (25), [funded_premium_book] VARCHAR (25), [premium_sales_book] VARCHAR (25), [financed_commissions_sales_book] VARCHAR (25), [premium_attribution_book] VARCHAR (25), [profit_attribution_book] VARCHAR (25), [depot_movement_book] VARCHAR (25), [quotation_book] VARCHAR (25), [interest_book] VARCHAR (25), [days_a_year] INTEGER NOT NULL, [age_days_a_year] NUMERIC (8, 4) NOT NULL, [unit_linked] BOOLEAN NOT NULL, [numbering_scheme] INTEGER NOT NULL, [profit_shared] BOOLEAN NOT NULL, [completion_book] VARCHAR (25), [repayment_book] VARCHAR (25), [additional_cost_book] VARCHAR (25), [transaction_book] VARCHAR (25), [company_code] VARCHAR (30), [transfer_book] VARCHAR (30), direct_debit_book character varying(25), PRIMARY KEY ([id]), FOREIGN KEY ([specialization_of_id]) REFERENCES [financial_product] ([id]) ON DELETE RESTRICT ON UPDATE CASCADE, CHECK (unit_linked IN ( 0 , 1 )), CHECK (profit_shared IN ( 0 , 1 )));






CREATE TABLE financial_account_role_feature
(
  value numeric(17,5) NOT NULL,
  described_by integer NOT NULL,
  id serial NOT NULL,
  of_id integer NOT NULL,
  CONSTRAINT financial_account_role_feature_pkey PRIMARY KEY (id),
  CONSTRAINT financial_account_role_feature_of_id_fkey FOREIGN KEY (of_id)
      REFERENCES financial_account_role (id) MATCH SIMPLE
      ON UPDATE CASCADE ON DELETE CASCADE
);
CREATE TABLE financial_product_book
(
  described_by integer NOT NULL,
  name character varying(25) NOT NULL,
  from_date date NOT NULL,
  thru_date date NOT NULL,
  id serial NOT NULL,
  financial_product_id integer NOT NULL,
  CONSTRAINT financial_product_book_pkey PRIMARY KEY (id),
  CONSTRAINT financial_product_book_financial_product_id_fk FOREIGN KEY (financial_product_id)
      REFERENCES financial_product (id) MATCH SIMPLE
      ON UPDATE CASCADE ON DELETE CASCADE
);
CREATE TABLE bank_natuurlijke_persoon
(
  id serial NOT NULL,
  perm_id integer,
  create_uid integer,
  create_date timestamp without time zone,
  write_date timestamp without time zone,
  write_uid integer,
  aktiviteit_sinds date,
  titel character varying(32),
  naam character varying(30) NOT NULL,
  huur_inkomsten double precision,
  adres_sinds date,
  postcode character varying(24),
  contract_type character varying(50),
  alimentatie_lasten double precision,
  identiteitskaart_datum date,
  kredietkaarten boolean,
  andere_inkomsten double precision,
  telefoon_werk character varying(64),
  identiteitskaart_nummer character varying(30),
  toestand_moeder character varying(22),
  nationaliteit integer,
  alimentatie_inkomsten double precision,
  werkgever_sinds date,
  kinderbijslag double precision,
  toekomstige_lasten double precision,
  beroeps_inkomsten double precision,
  email character varying(64),
  burgerlijke_staat_sinds date,
  werkgever character varying(40),
  fax character varying(64),
  beroep character varying(50),
  aktiviteit character varying(40),
  geboorteplaats character varying(30),
  toestand_vader character varying(22),
  vervangings_inkomsten double precision,
  voornaam character varying(30) NOT NULL,
  contract_toestand character varying(50),
  straat character varying(128),
  huur_lasten double precision,
  gemeente character varying(128),
  land integer,
  nationaal_nummer character varying(20),
  gender character varying(16),
  functie integer,
  geboortedatum date NOT NULL,
  btw_nummer character varying(15),
  huwelijkscontract character varying(40),
  telefoon character varying(64),
  andere_lasten double precision,
  toekomstige_inkomsten double precision,
  gsm character varying(64),
  burgerlijke_staat character varying(16),
  aankomstdatum date,
  language character varying(16) NOT NULL,
  pasfoto bytea,
  feitelijk_rechtspersoon boolean,
  verplaatst_naar integer,
  datum_verplaatsing date,
  kredietcentrale_geverifieerd character varying(16),
  kinderen_ten_laste_onbekend integer,
  beroepsinkomsten_bewezen character varying(17),
  name character varying(128),
  beroepsinkomsten_bewijs character varying(1024),
  kredietcentrale_verificatie character varying(1024),
  identiteitskaart character varying(1024),
  verplaats_naar_natuurlijke_persoon integer,
  active boolean,
  partner_id integer,
  correspondentie_land integer,
  datum_overlijden date,
  akte_bekendheid_overlijden character varying(100),
  rookgedrag boolean,
  origin character varying(50),
  nota text,
  correspondentie_straat character varying(128),
  correspondentie_postcode character varying(128),
  correspondentie_gemeente character varying(128),
  no_commercial_mailings boolean NOT NULL,
  tax_number character varying(40),
  bankrekening character varying(50),
  middle_name character varying(40),
  educational_level integer,
  fitness_level integer,
  public_figure integer,
  country_of_birth_id integer,
  nationaliteit_geographicboundary_id integer,
  geboorteplaats_id integer,
  CONSTRAINT bank_natuurlijke_persoon_pkey PRIMARY KEY (id),
  CONSTRAINT bank_natuurlijke_persoon_country_of_birth_id_fk FOREIGN KEY (country_of_birth_id)
      REFERENCES res_country (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT bank_natuurlijke_persoon_create_uid_fkey FOREIGN KEY (create_uid)
      REFERENCES res_users (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL,
  CONSTRAINT bank_natuurlijke_persoon_land_fkey FOREIGN KEY (land)
      REFERENCES res_country (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL,
  CONSTRAINT bank_natuurlijke_persoon_nationaliteit_fkey FOREIGN KEY (nationaliteit)
      REFERENCES res_country (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL,
  CONSTRAINT bank_natuurlijke_persoon_partner_id_fk FOREIGN KEY (partner_id)
      REFERENCES bank_natuurlijke_persoon (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT bank_natuurlijke_persoon_verplaats_naar_natuurlijke_persoo_fkey FOREIGN KEY (verplaats_naar_natuurlijke_persoon)
      REFERENCES bank_natuurlijke_persoon (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL,
  CONSTRAINT bank_natuurlijke_persoon_verplaatst_naar_fkey FOREIGN KEY (verplaatst_naar)
      REFERENCES bank_rechtspersoon (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL,
  CONSTRAINT bank_natuurlijke_persoon_write_uid_fkey FOREIGN KEY (write_uid)
      REFERENCES res_users (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL
)
CREATE TABLE bank_natuurlijke_persoon
(
  aktiviteit_sinds date,
  titel character varying(46),
  naam character varying(30) NOT NULL,
  adres_sinds date,
  postcode character varying(24),
  contract_type character varying(50),
  identiteitskaart_datum date,
  feitelijk_rechtspersoon boolean NOT NULL,
  telefoon_werk character varying(64),
  identiteitskaart_nummer character varying(30),
  taal character varying(50) NOT NULL,
  nationaliteit integer,
  datum_verplaatsing date,
  verplaats_naar_natuurlijke_persoon integer,
  werkgever_sinds date,
  email character varying(64),
  burgerlijke_staat_sinds date,
  werkgever character varying(40),
  fax character varying(64),
  beroep character varying(50),
  public_figure integer,
  aktiviteit character varying(40),
  geboorteplaats character varying(30),
  contract_toestand character varying(50),
  voornaam character varying(30) NOT NULL,
  middle_name character varying(40),
  active boolean,
  gemeente character varying(128),
  land integer,
  correspondentie_land integer,
  straat character varying(128),
  nationaal_nummer character varying(20),
  gender character varying(50),
  functie integer,
  geboortedatum date NOT NULL,
  btw_nummer character varying(15),
  huwelijkscontract character varying(50),
  aankomstdatum date,
  identiteitskaart character varying(100),
  gsm character varying(64),
  burgerlijke_staat character varying(50),
  telefoon character varying(64),
  datum_overlijden date,
  akte_bekendheid_overlijden character varying(100),
  no_commercial_mailings boolean NOT NULL,
  origin character varying(50),
  tax_number character varying(40),
  perm_id integer,
  id INTEGER PRIMARY KEY,
  partner_id integer,
  country_of_birth_id integer,
  nota text,
  correspondentie_straat character varying(128),
  correspondentie_postcode character varying(128),
  correspondentie_gemeente character varying(128),
  CONSTRAINT bank_natuurlijke_persoon_correspondentie_land_fk FOREIGN KEY (correspondentie_land)
      REFERENCES res_country (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT bank_natuurlijke_persoon_country_of_birth_id_fk FOREIGN KEY (country_of_birth_id)
      REFERENCES res_country (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT bank_natuurlijke_persoon_functie_fk FOREIGN KEY (functie)
      REFERENCES res_partner_function (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT bank_natuurlijke_persoon_land_fk FOREIGN KEY (land)
      REFERENCES res_country (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT bank_natuurlijke_persoon_nationaliteit_fk FOREIGN KEY (nationaliteit)
      REFERENCES res_country (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT bank_natuurlijke_persoon_partner_id_fk FOREIGN KEY (partner_id)
      REFERENCES bank_natuurlijke_persoon (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT bank_natuurlijke_persoon_verplaats_naar_natuurlijke_persoon_fk FOREIGN KEY (verplaats_naar_natuurlijke_persoon)
      REFERENCES bank_natuurlijke_persoon (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE NO ACTION
);
CREATE TABLE financial_agreement
(
  row_type character varying(40) NOT NULL,
  agreement_date date NOT NULL,
  from_date date NOT NULL,
  thru_date date NOT NULL,
  code character varying(20) NOT NULL,
  text text,
  package_id integer NOT NULL,
  document character varying(100),
  origin character varying(50),
  broker_relation_id integer,
  broker_agent_id integer,
  id INTEGER PRIMARY KEY,
  version_id INTEGER NOT NULL,
  kosten_andere numeric(17,2),
  kosten_bouwwerken numeric(17,2),
  schattingskosten numeric(17,2),
  ontvangen_voorschot numeric(17,2),
  kosten_architect numeric(17,2),
  kosten_btw numeric(17,2),
  eigen_middelen numeric(17,2),
  notariskosten_aankoop numeric(17,2),
  aankoopprijs numeric(17,2),
  verzekeringskosten numeric(17,2),
  wederbelegingsvergoeding numeric(17,2),
  achterstal_rekening character varying(4),
  kosten_verzekering numeric(17,2),
  achterstal numeric(17,2),
  handlichting numeric(17,2),
  notariskosten_hypotheek numeric(17,2),
  account_id integer,
  CONSTRAINT financial_agreement_account_id_fk FOREIGN KEY (account_id)
      REFERENCES financial_account (id) MATCH SIMPLE
      ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT financial_agreement_broker_agent_id_fkey FOREIGN KEY (broker_agent_id)
      REFERENCES bank_rechtspersoon (id) MATCH SIMPLE
      ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT financial_agreement_broker_relation_id_fkey FOREIGN KEY (broker_relation_id)
      REFERENCES bank_commercial_relation (id) MATCH SIMPLE
      ON UPDATE CASCADE ON DELETE RESTRICT,
  CONSTRAINT financial_agreement_package_id_fkey FOREIGN KEY (package_id)
      REFERENCES financial_package (id) MATCH SIMPLE
      ON UPDATE CASCADE ON DELETE RESTRICT
);
CREATE TABLE financial_agreement_role_feature
(
  value numeric(17,5) NOT NULL,
  described_by integer NOT NULL,
  id INTEGER PRIMARY KEY,
  of_id integer NOT NULL, reference CHARACTER VARYING(128),
  CONSTRAINT financial_agreement_role_feature_of_id_fkey FOREIGN KEY (of_id)
      REFERENCES financial_agreement_role (id) MATCH SIMPLE
      ON UPDATE CASCADE ON DELETE CASCADE
);
CREATE TABLE hypo_goed_aanvraag
(
  id INTEGER PRIMARY KEY,
  perm_id integer,
  create_uid integer,
  create_date timestamp without time zone,
  write_date timestamp without time zone,
  write_uid integer,
  te_hypothekeren_goed integer NOT NULL,
  hypothecaire_inschrijving double precision,
  hypothecair_mandaat double precision,
  aanhorigheden numeric(17,2),
  waarde_voor_werken numeric(17,2),
  waarde_verhoging numeric(17,2),
  prijs_grond numeric(17,2),
  financial_agreement_id integer NOT NULL,
  CONSTRAINT hypo_goed_aanvraag_create_uid_fkey FOREIGN KEY (create_uid)
      REFERENCES res_users (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL,
  CONSTRAINT hypo_goed_aanvraag_te_hypothekeren_goed_fkey FOREIGN KEY (te_hypothekeren_goed)
      REFERENCES hypo_te_hypothekeren_goed (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL,
  CONSTRAINT hypo_goed_aanvraag_write_uid_fkey FOREIGN KEY (write_uid)
      REFERENCES res_users (id) MATCH SIMPLE
      ON UPDATE NO ACTION ON DELETE SET NULL
);
COMMIT;
