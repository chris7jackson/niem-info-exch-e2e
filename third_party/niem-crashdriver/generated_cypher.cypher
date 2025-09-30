// Generated for CrashDriver1.xml using mapping
MERGE (n:`exch_CrashDriverInfo` {id:'syn_11d60c25b66b1fcc'})
  ON CREATE SET n.qname='exch:CrashDriverInfo', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_Crash` {id:'syn_631e7d7a239ea58d'})
  ON CREATE SET n.qname='j:Crash', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_ActivityLocation` {id:'syn_5d645adb711b765a'})
  ON CREATE SET n.qname='nc:ActivityLocation', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_Location2DGeospatialCoordinate` {id:'syn_bc00fac71cfaa165'})
  ON CREATE SET n.qname='nc:Location2DGeospatialCoordinate', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_GeographicCoordinateLatitude` {id:'syn_277be9ec6c065391'})
  ON CREATE SET n.qname='nc:GeographicCoordinateLatitude', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_GeographicCoordinateLongitude` {id:'syn_9c50655827022ac0'})
  ON CREATE SET n.qname='nc:GeographicCoordinateLongitude', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_CrashVehicle` {id:'syn_b5fef96b0bcbbe07'})
  ON CREATE SET n.qname='j:CrashVehicle', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_CrashDriver` {id:'syn_fde3f743a99096c8'})
  ON CREATE SET n.qname='j:CrashDriver', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_PersonName` {id:'syn_ec4ded6de496fc88'})
  ON CREATE SET n.qname='nc:PersonName', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_DriverLicense` {id:'syn_cc959d9639d3d1b8'})
  ON CREATE SET n.qname='j:DriverLicense', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_DriverLicenseCardIdentification` {id:'syn_b2c0e4a4ec48363f'})
  ON CREATE SET n.qname='j:DriverLicenseCardIdentification', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_CrashPerson` {id:'syn_87bcfb4d6ea1b993'})
  ON CREATE SET n.qname='j:CrashPerson', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_CrashPersonInjury` {id:'syn_b36c366503d06265'})
  ON CREATE SET n.qname='j:CrashPersonInjury', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_Charge` {id:'CH01'})
  ON CREATE SET n.qname='j:Charge', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_Person` {id:'syn_63c8560286adedbb'})
  ON CREATE SET n.qname='nc:Person', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_Charge` {id:'syn_54e5c6571709d83b'})
  ON CREATE SET n.qname='j:Charge', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_Metadata` {id:'JMD01'})
  ON CREATE SET n.qname='nc:Metadata', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`priv_PrivacyMetadata` {id:'PMD01'})
  ON CREATE SET n.qname='priv:PrivacyMetadata', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`priv_PrivacyMetadata` {id:'PMD02'})
  ON CREATE SET n.qname='priv:PrivacyMetadata', n.sourceDoc='CrashDriver1.xml';
MATCH (p:`exch_CrashDriverInfo` {id:'syn_11d60c25b66b1fcc'}), (c:`j_Crash` {id:'syn_631e7d7a239ea58d'}) MERGE (p)-[:`HAS_CRASH`]->(c);
MATCH (p:`j_Crash` {id:'syn_631e7d7a239ea58d'}), (c:`nc_ActivityLocation` {id:'syn_5d645adb711b765a'}) MERGE (p)-[:`HAS_ACTIVITYLOCATION`]->(c);
MATCH (p:`nc_ActivityLocation` {id:'syn_5d645adb711b765a'}), (c:`nc_Location2DGeospatialCoordinate` {id:'syn_bc00fac71cfaa165'}) MERGE (p)-[:`HAS_LOCATION2DGEOSPATIALCOORDINATE`]->(c);
MATCH (p:`nc_Location2DGeospatialCoordinate` {id:'syn_bc00fac71cfaa165'}), (c:`nc_GeographicCoordinateLatitude` {id:'syn_277be9ec6c065391'}) MERGE (p)-[:`HAS_GEOGRAPHICCOORDINATELATITUDE`]->(c);
MATCH (p:`nc_Location2DGeospatialCoordinate` {id:'syn_bc00fac71cfaa165'}), (c:`nc_GeographicCoordinateLongitude` {id:'syn_9c50655827022ac0'}) MERGE (p)-[:`HAS_GEOGRAPHICCOORDINATELONGITUDE`]->(c);
MATCH (p:`j_Crash` {id:'syn_631e7d7a239ea58d'}), (c:`j_CrashVehicle` {id:'syn_b5fef96b0bcbbe07'}) MERGE (p)-[:`HAS_CRASHVEHICLE`]->(c);
MATCH (p:`j_CrashVehicle` {id:'syn_b5fef96b0bcbbe07'}), (c:`j_CrashDriver` {id:'syn_fde3f743a99096c8'}) MERGE (p)-[:`HAS_CRASHDRIVER`]->(c);
MATCH (p:`j_CrashDriver` {id:'syn_fde3f743a99096c8'}), (c:`nc_PersonName` {id:'syn_ec4ded6de496fc88'}) MERGE (p)-[:`HAS_PERSONNAME`]->(c);
MATCH (p:`j_CrashDriver` {id:'syn_fde3f743a99096c8'}), (c:`j_DriverLicense` {id:'syn_cc959d9639d3d1b8'}) MERGE (p)-[:`HAS_DRIVERLICENSE`]->(c);
MATCH (p:`j_DriverLicense` {id:'syn_cc959d9639d3d1b8'}), (c:`j_DriverLicenseCardIdentification` {id:'syn_b2c0e4a4ec48363f'}) MERGE (p)-[:`HAS_DRIVERLICENSECARDIDENTIFICATION`]->(c);
MATCH (p:`j_Crash` {id:'syn_631e7d7a239ea58d'}), (c:`j_CrashPerson` {id:'syn_87bcfb4d6ea1b993'}) MERGE (p)-[:`HAS_CRASHPERSON`]->(c);
MATCH (p:`j_CrashPerson` {id:'syn_87bcfb4d6ea1b993'}), (c:`j_CrashPersonInjury` {id:'syn_b36c366503d06265'}) MERGE (p)-[:`HAS_CRASHPERSONINJURY`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'syn_11d60c25b66b1fcc'}), (c:`j_Charge` {id:'CH01'}) MERGE (p)-[:`HAS_CHARGE`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'syn_11d60c25b66b1fcc'}), (c:`nc_Person` {id:'syn_63c8560286adedbb'}) MERGE (p)-[:`HAS_PERSON`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'syn_11d60c25b66b1fcc'}), (c:`j_Charge` {id:'syn_54e5c6571709d83b'}) MERGE (p)-[:`HAS_CHARGE`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'syn_11d60c25b66b1fcc'}), (c:`nc_Metadata` {id:'JMD01'}) MERGE (p)-[:`HAS_METADATA`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'syn_11d60c25b66b1fcc'}), (c:`priv_PrivacyMetadata` {id:'PMD01'}) MERGE (p)-[:`HAS_PRIVACYMETADATA`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'syn_11d60c25b66b1fcc'}), (c:`priv_PrivacyMetadata` {id:'PMD02'}) MERGE (p)-[:`HAS_PRIVACYMETADATA`]->(c);