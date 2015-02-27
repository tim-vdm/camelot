#!/usr/bin/env python
import requests
import json

DOCUMENT = {
	"agent_official_number_fsma": "128Char",
	"agreement_date": {
		"month": 3, 
		"year": 2015,
		"day": 2
	},
	"duration": 10,
	"from_date": {
		"month": 3,
		"year": 2015,
		"day": 1
	},
	"insured_party__1__birthdate": {
		"month": 9,
		"year": 1980,
		"day": 15
	},
	"insured_party__1__sex": "M",
	"package_id": 64,
	"premium_schedule__1__premium_fee_1": "2.00",
	"premium_schedule__1__product_id": 67,
	"premium_schedule__2__product_id": None,
	"premium_schedules_coverage_level_type": "fixed_amount",
	"premium_schedules_coverage_limit": "5000",
	"premium_schedules_payment_duration": 10,
	"premium_schedules_period_type": "single",
	"premium_schedules_premium_rate_1": "20",
	"origin": "BIA:-10",
}

if __name__ == '__main__':
	response = requests.post('http://staging-patronale-life.mgx.io/api/v0.1/create_agreement_code',
	# response = requests.post(
		# 'http://localhost:19021/api/v0.1/calculate_proposal',
		headers={'content-type': 'application/json'},
		data=json.dumps(DOCUMENT),
	)

	print response.status_code
	print response.json()
