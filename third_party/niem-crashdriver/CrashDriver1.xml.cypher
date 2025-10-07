// Generated for CrashDriver1.xml using mapping
MERGE (n:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'})
  ON CREATE SET n.qname='exch:CrashDriverInfo', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_Crash` {id:'c3143674_syn_ee7eee444bc0b5ee'})
  ON CREATE SET n.qname='j:Crash', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_ActivityDate` {id:'c3143674_syn_71215f405f3c2a06'})
  ON CREATE SET n.qname='nc:ActivityDate', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_ActivityLocation` {id:'c3143674_syn_8247c00fc6e474e0'})
  ON CREATE SET n.qname='nc:ActivityLocation', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_Location2DGeospatialCoordinate` {id:'c3143674_syn_bce6b05f4a66dcd5'})
  ON CREATE SET n.qname='nc:Location2DGeospatialCoordinate', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_GeographicCoordinateLatitude` {id:'c3143674_syn_3ef306d34c8e0c20'})
  ON CREATE SET n.qname='nc:GeographicCoordinateLatitude', n.sourceDoc='CrashDriver1.xml', n.nc_LatitudeDegreeValue='51.87';
MERGE (n:`nc_GeographicCoordinateLongitude` {id:'c3143674_syn_30d7bd9068cb3477'})
  ON CREATE SET n.qname='nc:GeographicCoordinateLongitude', n.sourceDoc='CrashDriver1.xml', n.nc_LongitudeDegreeValue='-1.28';
MERGE (n:`j_CrashVehicle` {id:'c3143674_syn_46624521ab8b1daf'})
  ON CREATE SET n.qname='j:CrashVehicle', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_Person` {id:'c3143674_P01'})
  ON CREATE SET n.qname='nc:Person', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`Augmentation` {id:'c3143674_syn_1299ec91a67ae87a'})
  ON CREATE SET n.qname='j:PersonAugmentation', n.sourceDoc='CrashDriver1.xml', n.j_PersonAdultIndicator='true';
MERGE (n:`j_CrashDriver` {id:'c3143674_syn_4c71c3fb05d13ad3'})
  ON CREATE SET n.qname='j:CrashDriver', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_PersonBirthDate` {id:'c3143674_syn_0ab8db7f2a185b78'})
  ON CREATE SET n.qname='nc:PersonBirthDate', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`nc_PersonName` {id:'c3143674_syn_193fd237d96677b1'})
  ON CREATE SET n.qname='nc:PersonName', n.sourceDoc='CrashDriver1.xml', n.nc_PersonGivenName='Peter', n.nc_PersonMiddleName='Death', n.nc_PersonSurName='Wimsey';
MERGE (n:`j_DriverLicense` {id:'c3143674_syn_a04b5b9dbe3e6c3b'})
  ON CREATE SET n.qname='j:DriverLicense', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_DriverLicenseCardIdentification` {id:'c3143674_syn_73cebe83e9ec6953'})
  ON CREATE SET n.qname='j:DriverLicenseCardIdentification', n.sourceDoc='CrashDriver1.xml', n.nc_IdentificationID='A1234567';
MERGE (n:`j_CrashPerson` {id:'c3143674_syn_a7c061d504506238'})
  ON CREATE SET n.qname='j:CrashPerson', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`j_CrashPersonInjury` {id:'c3143674_syn_d0ea5936bf2d4def'})
  ON CREATE SET n.qname='j:CrashPersonInjury', n.sourceDoc='CrashDriver1.xml', n.nc_InjuryDescriptionText='Broken Arm';
MERGE (n:`j_Charge` {id:'c3143674_CH01'})
  ON CREATE SET n.qname='j:Charge', n.sourceDoc='CrashDriver1.xml', n.j_ChargeDescriptionText='Furious Driving', n.j_ChargeFelonyIndicator='false';
MERGE (n:`j_PersonChargeAssociation` {id:'c3143674_syn_fc3e249a04245612'})
  ON CREATE SET n.qname='j:PersonChargeAssociation', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`Augmentation` {id:'c3143674_syn_a061e985a69f43f6'})
  ON CREATE SET n.qname='j:MetadataAugmentation', n.sourceDoc='CrashDriver1.xml', n.j_CriminalInformationIndicator='true';
MERGE (n:`nc_Metadata` {id:'c3143674_JMD01'})
  ON CREATE SET n.qname='nc:Metadata', n.sourceDoc='CrashDriver1.xml';
MERGE (n:`priv_PrivacyMetadata` {id:'c3143674_PMD01'})
  ON CREATE SET n.qname='priv:PrivacyMetadata', n.sourceDoc='CrashDriver1.xml', n.priv_PrivacyCode='PII';
MERGE (n:`priv_PrivacyMetadata` {id:'c3143674_PMD02'})
  ON CREATE SET n.qname='priv:PrivacyMetadata', n.sourceDoc='CrashDriver1.xml', n.priv_PrivacyCode='MEDICAL';
MATCH (p:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'}), (c:`j_Crash` {id:'c3143674_syn_ee7eee444bc0b5ee'}) MERGE (p)-[:`HAS_CRASH`]->(c);
MATCH (p:`j_Crash` {id:'c3143674_syn_ee7eee444bc0b5ee'}), (c:`nc_ActivityDate` {id:'c3143674_syn_71215f405f3c2a06'}) MERGE (p)-[:`HAS_ACTIVITYDATE`]->(c);
MATCH (p:`j_Crash` {id:'c3143674_syn_ee7eee444bc0b5ee'}), (c:`nc_ActivityLocation` {id:'c3143674_syn_8247c00fc6e474e0'}) MERGE (p)-[:`HAS_ACTIVITYLOCATION`]->(c);
MATCH (p:`nc_ActivityLocation` {id:'c3143674_syn_8247c00fc6e474e0'}), (c:`nc_Location2DGeospatialCoordinate` {id:'c3143674_syn_bce6b05f4a66dcd5'}) MERGE (p)-[:`HAS_LOCATION2DGEOSPATIALCOORDINATE`]->(c);
MATCH (p:`nc_Location2DGeospatialCoordinate` {id:'c3143674_syn_bce6b05f4a66dcd5'}), (c:`nc_GeographicCoordinateLatitude` {id:'c3143674_syn_3ef306d34c8e0c20'}) MERGE (p)-[:`HAS_GEOGRAPHICCOORDINATELATITUDE`]->(c);
MATCH (p:`nc_Location2DGeospatialCoordinate` {id:'c3143674_syn_bce6b05f4a66dcd5'}), (c:`nc_GeographicCoordinateLongitude` {id:'c3143674_syn_30d7bd9068cb3477'}) MERGE (p)-[:`HAS_GEOGRAPHICCOORDINATELONGITUDE`]->(c);
MATCH (p:`j_Crash` {id:'c3143674_syn_ee7eee444bc0b5ee'}), (c:`j_CrashVehicle` {id:'c3143674_syn_46624521ab8b1daf'}) MERGE (p)-[:`HAS_CRASHVEHICLE`]->(c);
MATCH (p:`Unknown` {id:'c3143674_syn_4c71c3fb05d13ad3'}), (c:`Augmentation` {id:'c3143674_syn_1299ec91a67ae87a'}) MERGE (p)-[:`AugmentedBy`]->(c);
MATCH (p:`j_CrashVehicle` {id:'c3143674_syn_46624521ab8b1daf'}), (c:`j_CrashDriver` {id:'c3143674_syn_4c71c3fb05d13ad3'}) MERGE (p)-[:`HAS_CRASHDRIVER`]->(c);
MATCH (p:`j_CrashDriver` {id:'c3143674_syn_4c71c3fb05d13ad3'}), (c:`nc_PersonBirthDate` {id:'c3143674_syn_0ab8db7f2a185b78'}) MERGE (p)-[:`HAS_PERSONBIRTHDATE`]->(c);
MATCH (p:`j_CrashDriver` {id:'c3143674_syn_4c71c3fb05d13ad3'}), (c:`nc_PersonName` {id:'c3143674_syn_193fd237d96677b1'}) MERGE (p)-[:`HAS_PERSONNAME`]->(c);
MATCH (p:`j_CrashDriver` {id:'c3143674_syn_4c71c3fb05d13ad3'}), (c:`j_DriverLicense` {id:'c3143674_syn_a04b5b9dbe3e6c3b'}) MERGE (p)-[:`HAS_DRIVERLICENSE`]->(c);
MATCH (p:`j_DriverLicense` {id:'c3143674_syn_a04b5b9dbe3e6c3b'}), (c:`j_DriverLicenseCardIdentification` {id:'c3143674_syn_73cebe83e9ec6953'}) MERGE (p)-[:`HAS_DRIVERLICENSECARDIDENTIFICATION`]->(c);
MATCH (p:`j_Crash` {id:'c3143674_syn_ee7eee444bc0b5ee'}), (c:`j_CrashPerson` {id:'c3143674_syn_a7c061d504506238'}) MERGE (p)-[:`HAS_CRASHPERSON`]->(c);
MATCH (p:`j_CrashPerson` {id:'c3143674_syn_a7c061d504506238'}), (c:`j_CrashPersonInjury` {id:'c3143674_syn_d0ea5936bf2d4def'}) MERGE (p)-[:`HAS_CRASHPERSONINJURY`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'}), (c:`j_Charge` {id:'c3143674_CH01'}) MERGE (p)-[:`HAS_CHARGE`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'}), (c:`j_PersonChargeAssociation` {id:'c3143674_syn_fc3e249a04245612'}) MERGE (p)-[:`HAS_PERSONCHARGEASSOCIATION`]->(c);
MATCH (p:`j_PersonChargeAssociation` {id:'c3143674_syn_fc3e249a04245612'}), (c:`nc_Person` {id:'c3143674_P01'}) MERGE (p)-[:`HAS_PERSON`]->(c);
MATCH (p:`j_PersonChargeAssociation` {id:'c3143674_syn_fc3e249a04245612'}), (c:`j_Charge` {id:'c3143674_CH01'}) MERGE (p)-[:`HAS_CHARGE`]->(c);
MATCH (p:`Unknown` {id:'c3143674_JMD01'}), (c:`Augmentation` {id:'c3143674_syn_a061e985a69f43f6'}) MERGE (p)-[:`AugmentedBy`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'}), (c:`nc_Metadata` {id:'c3143674_JMD01'}) MERGE (p)-[:`HAS_METADATA`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'}), (c:`priv_PrivacyMetadata` {id:'c3143674_PMD01'}) MERGE (p)-[:`HAS_PRIVACYMETADATA`]->(c);
MATCH (p:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'}), (c:`priv_PrivacyMetadata` {id:'c3143674_PMD02'}) MERGE (p)-[:`HAS_PRIVACYMETADATA`]->(c);
MATCH (a:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'}), (b:`j_Charge` {id:'c3143674_CH01'}) MERGE (a)-[:`J_CHARGE`]->(b);
MATCH (a:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'}), (b:`nc_Metadata` {id:'c3143674_JMD01'}) MERGE (a)-[:`NC_METADATA`]->(b);
MATCH (a:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'}), (b:`priv_PrivacyMetadata` {id:'c3143674_PMD01'}) MERGE (a)-[:`PRIV_PRIVACYMETADATA`]->(b);
MATCH (a:`exch_CrashDriverInfo` {id:'c3143674_syn_11d60c25b66b1fcc'}), (b:`priv_PrivacyMetadata` {id:'c3143674_PMD02'}) MERGE (a)-[:`PRIV_PRIVACYMETADATA`]->(b);
MATCH (a:`j_CrashDriver` {id:'c3143674_syn_4c71c3fb05d13ad3'}), (b:`nc_Person` {id:'c3143674_P01'}) MERGE (a)-[:`REPRESENTS_PERSON`]->(b);
MATCH (a:`j_CrashPerson` {id:'c3143674_syn_a7c061d504506238'}), (b:`nc_Person` {id:'c3143674_P01'}) MERGE (a)-[:`REPRESENTS_PERSON`]->(b);