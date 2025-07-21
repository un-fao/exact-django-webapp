## 1.14.6 (2025-07-21)

### Feat

- add script to convert vc storage refrigerant ef from kg to tonnes

### Fix

- missing specification of request owner in activity copy endpoint
- **calculators**: align agb max label to the new one in the model

## 1.14.5 (2025-07-18)

### Feat

- add agb and bgb max tier 2 values in ForestManagement model

### Fix

- **calculators**: forcibly set disturbance arrays to zero when empty in ForestManagementCalculator
- **calculators**: forcibly set agb tier2 values to zero for afforestation
- wrong t2 emission factor references in EnergyEntryCalculator
- small fishery gear types script not counting unmotorized fishing

## 1.14.4 (2025-07-17)

### Feat

- add update_module_types_of_fuel_types function and FuelType_ModuleType.csv data

### Fix

- refactor migrations to avoid useless mass uuid assignment
- remove call to change_other_land_flu_data_to_1 in development mode

## 1.14.3 (2025-07-17)

### Feat

- add script to correct other land flu data
- add fishery type - small fishery gear type relations
- add fishery type m2m link in the small fishery gear type model
- **filtering**: add support for m2m fields in DynamicSearchAndFilterBackend
- add script to remove irrigation modules from wood peat and charcoal
- **public**: set uuid as project lookup field in public endpoint
- add hih assessment data structure and endpoint
- **reports**: add french templated report
- add better error message when trying to delete a project with multiple admins

### Fix

- logcal error preventing deletion of other people from project where user had admin rights
- remove public id from project model
- **reports**: spanish template not showing all activities
- **reports**: templated report not showing all activities
- **reports**: missing energy entry reference in energy and valuechain reports
- **reports**: offset module emissions in excel
- **copy**: activity reference for submodules when handling comment threads
- **reports**: offset activity emissions in excel

## 1.14.2 (2025-07-09)

### Feat

- **login**: better error handling and messages when login fails

### Fix

- **copy**: solve issue with comment threads and prevent copying comments without the right permissions
- prevent failed project copy from persisting the broken project
- **calculators**: set irrigation phase ch4 and n2o efs to zero when electricity or renewable
- **defaults**: add missing values to irrigation phase defaults
- **reports**: Update ExcelFileManager to disable file saving on disk

## 1.14.1 (2025-05-30)

## 1.14 (2025-05-29)

### Feat

- add value chain modules reports

### Fix

- add missing electricity emissions row population in smal and large fishery reports
- add missing units for modules remaining modules in templated report
- issue with comment threads causing crash during project and activity copy

## 1.13.15 (2025-05-19)

### Fix

- add map data in changes to exclude from get_changes

## 1.13.14 (2025-05-19)

### Fix

- typo causing aquaculture and fishery data not to show up in template units table
- correctly skip module results with errors instead of trying to access them in the templated report
- delete unused files

## 1.13.13 (2025-05-19)

### Feat

- show entity names instead of ids in changelog

### Fix

- **math**: logical error in forest management logging or recurrence checks

## 1.13.12 (2025-05-19)

### Fix

- minor queryset bugs in project and activity

## 1.13.11 (2025-05-17)

### Feat

- add id to membership serializer

### Fix

- unchecked None threads causing crash when sending recaps for entities with uninitialized threads
- public activities list endpoint filters

## 1.13.10 (2025-05-14)

### Fix

- use prefiltered queryset to avoid showing non-public entities

## 1.13.9 (2025-05-14)

### Feat

- add serialized status object in public module serializer

## 1.13.8 (2025-05-14)

### Feat

- add module type to generic public module serializer

## 1.13.7 (2025-05-14)

### Fix

- make soil type viewset public
- remove permission check from public defaults endpoint

## 1.13.6 (2025-05-14)

### Fix

- cut action type definition from generic public serializer call

## 1.13.5 (2025-05-14)

### Fix

- module retrieval in public module viewset

## 1.13.4 (2025-05-14)

### Fix

- account for superuser edits in recap email
- add accidentally removed router endpoints

## 1.13.3 (2025-05-13)

### Feat

- add activities endpoint to public project viewset
- add excel and templated reports to public project viewset
- add scenario based complete renewal in perennial cropland

### Fix

- make all public project fields visible and exclude specific ones
- typo in organic soil drainage t2 references
- threads property getter in module abstract model
- add missing public module endpoints

## 1.13.2 (2025-05-12)

### Feat

- add missing public endpoints
- add more information ton public activity endpoint
- add all public modules endpoints

## 1.13.1 (2025-05-12)

### Feat

- finish setting informational endpoints as public

## 1.13 (2025-05-12)

### Feat

- add modules action to public activity viewset
- make all "-types" endpoints public

## 1.12.3 (2025-05-12)

### Fix

- remove skipping results calculation for archived projects

## 1.12.2a (2025-05-09)

### Feat

- add history of comments to changes recap email
- automatically un-finalize copied projects
- send changes recap email to project admins on project is unlocked

### Fix

- missing inclusion of renewables in irrigation phase calculator
- organic soil drainage t2 field names
- project lock not being updated during activity, modules and submodules writes

## 1.12.2 (2025-05-05)

### Feat

- add parametric storage bucket name in project attachment viewset

### Fix

- prevent empty threads from crashing project copy

## 1.12.1 (2025-04-30)

### Fix

- migrations and deploy script
- some typos in russian translation files

## 1.12 (2025-04-30)

### Feat

- add revised russian translations
- add new french translations
- add energy entry defaults

### Fix

- versioning
- energy default testing suite
- missing populate_metadata method in flooded rice report class
- type error caused by activity duration t2 being None
- missing delete method in activity delete
- typo in retrieval of project from context in project file upload serializer
- add script to fill out missing emission factor sources from irrigation phases with new energy component

## 1.11.2 (2025-04-25)

### Feat

- add datasource endpoint

### Fix

- remove cache changes from module history changelog and skip records with user None

## 1.11.1 (2025-04-25)

### Feat

- activate review github action?

## 1.11 (2025-04-25)

### Feat

- add fao logo in spanish
- add filled french translations
- add more granular information on activity impact in templated scenario
- pass max bgb to mathematical model in forest management calculator
- implement BGBMax as pseudo-tier2 value in forest management mathematical model
- set missing FRA reference values to zero in forest management calculator
- use of data from FRA when selected as a datasource in forest management calculator
- add short name to datasource model
- add data source attribute to all modules and submodules
- add FRA carbon stock data for year 2020
- add multilanguage support for templated reports
- sort activities and modules relative to carbon balance sign in templated report

### Fix

- cut all translation wildcards from api models
- add request language as default templated report language
- properly parse class names with acronyms in url name generator
- change uniqueness rules of datasource model
- issue with country attribute in base calculator causing country to be None
- apply latest corrections to spanish templated report
- prevent copying activities in a finalized or archived project and add missing comment threads copying logic
- prevent file uploads to finalized projects
- block deletion of activities in finalized projects

## 1.10.1 (2025-04-17)

### Fix

- translation script in bitbucket pipeline

## 1.10 (2025-04-17)

### Feat

- add russian language support
- add packaging material types translations
- add text placeholder for activities with no hectares, catch or heads
- add generic model admin adding export to csv and dynamic search
- add search bar and csv export for CustomUserAdmin

### Fix

- replace TillageType with TillageManagementType in translations
- skip removed entries and allow for ipcc models to be included
- minitool region reference in csv

## 1.9.5 (2025-04-11)

### Feat

- integrate energy emission factor in irrigation phase calculator

### Fix

- cut useless and problematic validation of activity in activity builder
- country_t2 not overriding project country in energy and vc calculations and thus in defaults

## 1.9.4 (2025-04-10)

### Fix

- add pagination queryparams to ignored keys in project dynamic filtering

## 1.9.3c (2025-04-09)

### Fix

- add setuptools and wheel update in pipeline

## 1.9.3b (2025-04-09)

### Feat

- change pip install command to prefer binary and use legacy resolver in pipeline configuration

## 1.9.3a (2025-04-09)

### Fix

- add pip upgrade in pipeline steps

## 1.9.3 (2025-04-09)

### Feat

- allow admins to send invitations and create memberships for finalized projects
- add is_finalized to project summary serializer
- add dynamic filters to project viewset
- prevent project archiving if there are multiple admins

### Fix

- deduplicate projects by only allowing unique ids when filtering user memberships
- add missing validation of existing activity in activity builder
- check that new last year of accounting for the project is not lower than the duretion of its activities

## 1.9.2 (2025-04-08)

### Fix

- add id field in project tags action response