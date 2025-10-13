# Demo Key Points and Highlights

1. Upload a schema folder
    a. Upload
        i. Select folder containing all *.xsd files included in schema
        ii. Files that are not *.xsd will be ignored from validation (include in upload)
        iii. Select the primary iepd xsd file that the CMF tool will use for conversion
    b. Validation
        i. NDR Validation: Each *.xsd file is validated against NIEM naming design rules for 6.0 is by executing via schematron the rules applicable to each file's confromance target (i.e. reference, extension, or subset schemas). The validator comes directly from NIEM Naming Design Rules Respository 
            - Option to SKIP NDR validation. 
        ii. Import Validation: All defined imports and name spaces defined in the each *.xsd file are validated to ensure that the uploaded schema folder is complete. 
    c. Error Handling
        i. The failing rules or warnings are shown by file 
        ii. The failing imports and files expected to exist are shown by file
2. View Generated files @ Minio Browser (localhost/9002)
    a. XSD -> CMF
        i. {primary_schema}.cmf (e.g., CrashDriver.cmf)
    b. CMF -> JSON LD
        i. {primary_schema}.json (e.g., CrashDriver.json)
    c. Mapping.Yaml
3. Upload Instance Documents
    a. Can upload multiple files at once. Any errors will just stop the upload of the invalid file
    a. XML Upload
        i. Doesn't allow for unknown fields at all. 
    c. JSON Upload
        i. No required fields in json schema. Hence only existing fields are run through validation. An instance document without any related fields will pass. 
4. Graph Visualization @ Neo4j Browser (localhost/7474) 
    a. XML Data Ingestion 
        i. augmentation nodes don't have parent node
        ii. Double relationships between root node and children. 
    b. JSON Data Ingestion 
        i. Augmentations, Associations, and Root Level Node names are showing as ne4j ids rather than qualified names
5. Admin Reset
    a. Dry run confirmation after viewing documents to be permanently deleted. 


TODO: 
- upload - keep all schema files, just ignore non-xsd files.
- Show NDR validation error against exact line anad location found. (enh)
- Visually show that the json is being validated against json ld schema generated via cmf tool. 
    - show confirmation screen. 
- Show option to view generated files associated with uploaded schemas. 
- Block same document or exactly same schema set from being uploaded multiple times? 
- GRAPH
    - Ensure XML data ingestion 
- File Management
    - can name schema set for iepd. 
- Security Hardening 
    - SSL 
    - Data encryption in transit
    - Data encryption at rest
    

- data import wizad
- select fields 
- use shema structure
    - tell me all the relatinsihps by entities
    - assocation types
    - 



- interface to manage cmf? what if I'm using cmf to model usign UML or new exch 
- file mgmt for keeping track of cmf workflow
    - browse cmf across files 

- eng with federal agency. 10 eeg, 3 clients, roll up same reporting line
    if I have to manage the build 10 iepds. 
    xsd to json should show differnt file name. 


augmentation point - is a 
associations are rich content edges (should it be a node or just a rich edge?)
references are edgse. 

- quicly 
- tree. 
    - cmf show as a tree.
    - xsd starts with a root and builds a tree which is exactly a knoweldge graph
    - models don't always have that same structure.
    on the smae level. entty, entity, association. 
        node type a, node type b. 
        define an edge. 
        probably want to model the RDF description. 


    - RDF. 