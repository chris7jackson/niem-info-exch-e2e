<?xml version="1.0" encoding="UTF-8"?>
<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron"
            xmlns:xs="http://www.w3.org/2001/XMLSchema"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xmlns:structures="https://docs.oasis-open.org/niemopen/ns/model/structures/6.0/"
            xmlns:nf="urn:ndr:functions"           <!-- interface -->
            queryBinding="xslt2">

  <!-- Import the NIEM function library -->
  <sch:ns prefix="nf" uri="urn:ndr:functions"/>
  <sch:extends href="ndr-functions-interface.xsl"/>

  <!-- Pass your XML catalog at runtime: xml-catalog=doc('catalog.xml') -->
  <sch:let name="catalog" value="document('')/*"/> <!-- placeholder; Saxon param overrides -->

  <!-- Utility: resolve this element’s declaration in the schema set -->
  <sch:let name="decl"
           value="nf:resolve-element(., QName(namespace-uri(.), local-name(.)))"/>

  <!-- 1) xsi:nil only when the schema element is nillable -->
  <sch:pattern id="xsi-nil-nillable">
    <sch:rule context="*[@xsi:nil='true']">
      <sch:assert test="$decl/@nillable = 'true'">
        Element <sch:value-of select="name()"/> is nilled but its declaration is not nillable.
      </sch:assert>
      <sch:assert test="not(node())">
        Nilled element <sch:value-of select="name()"/> must be empty.
      </sch:assert>
    </sch:rule>
  </sch:pattern>

  <!-- 2) structures:ref rules -->
  <sch:pattern id="structures-ref">
    <sch:rule context="*[@structures:ref]">
      <sch:assert test="not(node()) and not(@structures:id)">
        An element with @structures:ref must be empty and must not also carry @structures:id.
      </sch:assert>
      <sch:assert test="//*[@structures:id = current()/@structures:ref]">
        @structures:ref must reference an existing @structures:id in this document.
      </sch:assert>
    </sch:rule>
  </sch:pattern>

  <!-- 3) No direct use of abstract elements/types -->
  <sch:pattern id="no-abstract">
    <sch:rule context="*">
      <sch:assert test="not($decl/@abstract='true')">
        Element <sch:value-of select="name()"/> resolves to an abstract declaration and cannot appear directly.
      </sch:assert>
    </sch:rule>
  </sch:pattern>

  <!-- 4) (Example) If schema says simple content, enforce scalar-like instance shape -->
  <sch:pattern id="simple-content-shape">
    <sch:rule context="*">
      <sch:let name="type" value="nf:resolve-type(., resolve-QName($decl/@type, $decl))"/>
      <sch:assert test="not($type/xs:simpleContent) or (not(*) and not(@structures:ref))">
        Elements of simple content types should not carry child elements.
      </sch:assert>
    </sch:rule>
  </sch:pattern>

</sch:schema>