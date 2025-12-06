<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:tei="http://www.tei-c.org/ns/1.0"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    exclude-result-prefixes="tei xs">

    <xsl:output method="xml" indent="yes" encoding="UTF-8"/>

    <!-- Root template -->
    <xsl:template match="/">
        <TEI xmlns="http://www.tei-c.org/ns/1.0">
            <teiHeader>
                <fileDesc>
                    <titleStmt>
                        <title>Personenregister Conrad Ansorge</title>
                        <author>Christian Heitler und Eike Rathgeber</author>
                    </titleStmt>
                    <publicationStmt>
                        <p>Erstellt aus PDF-Export, transformiert zu TEI</p>
                    </publicationStmt>
                    <sourceDesc>
                        <p>Konvertiert aus index-pdf-export.xml</p>
                    </sourceDesc>
                </fileDesc>
            </teiHeader>
            <text>
                <body>
                    <listPerson>
                        <xsl:apply-templates select="//P[not(@type) or @type='person']"/>
                    </listPerson>

                    <div type="references">
                        <xsl:apply-templates select="//P[@type='ref']"/>
                    </div>

                    <listOrg>
                        <xsl:apply-templates select="//P[@type='org']"/>
                    </listOrg>
                </body>
            </text>
        </TEI>
    </xsl:template>

    <!-- Template for reference entries (type='ref') -->
    <xsl:template match="P[@type='ref']">
        <xsl:variable name="text" select="normalize-space(.)"/>

        <!-- Parse reference: extract source and target -->
        <!-- Pattern: "Source →Target" or "Source. Siehe →Target" -->
        <xsl:analyze-string select="$text" regex="^([^→]+).*?→\s*(.+?)\s*\.?\s*$">
            <xsl:matching-substring>
                <xsl:variable name="sourceName" select="normalize-space(regex-group(1))"/>
                <xsl:variable name="targetName" select="normalize-space(regex-group(2))"/>

                <ref xmlns="http://www.tei-c.org/ns/1.0" type="see">
                    <xsl:attribute name="source" select="$sourceName"/>
                    <xsl:attribute name="target" select="$targetName"/>
                    <xsl:value-of select="$text"/>
                </ref>
            </xsl:matching-substring>
        </xsl:analyze-string>
    </xsl:template>

    <!-- Template for organization entries (type='org') -->
    <xsl:template match="P[@type='org']">
        <xsl:variable name="text" select="normalize-space(.)"/>
        <xsl:variable name="currentNode" select="."/>
        <xsl:variable name="orgId" select="generate-id($currentNode)"/>

        <!-- Extract page numbers -->
        <xsl:variable name="pages" select="if (matches($text, '\.[\s\p{L}]*[\s,]*[\d,\s]+$'))
                                           then replace($text, '^.*?\.\s*[^\d]*?([\d,\s]+)$', '$1')
                                           else ''"/>

        <!-- Extract organization name and description -->
        <xsl:variable name="textWithoutPages" select="if ($pages != '')
                                                       then replace($text, '(\..*?)([\d,\s]+)$', '$1')
                                                       else $text"/>

        <!-- Extract name (quoted part) and description -->
        <xsl:analyze-string select="$textWithoutPages" regex="^[&#x201E;&#x201C;&quot;]([^&quot;&#x201C;]+)[&#x201C;&quot;]\s*\.?\s*(.*)$">
            <xsl:matching-substring>
                <xsl:variable name="orgName" select="regex-group(1)"/>
                <xsl:variable name="description" select="normalize-space(regex-group(2))"/>

                <org xmlns="http://www.tei-c.org/ns/1.0">
                    <xsl:attribute name="xml:id">
                        <xsl:value-of select="concat('org_', $orgId)"/>
                    </xsl:attribute>

                    <orgName>
                        <xsl:value-of select="$orgName"/>
                    </orgName>

                    <xsl:if test="$description != ''">
                        <note>
                            <xsl:value-of select="$description"/>
                        </note>
                    </xsl:if>

                    <!-- Add page numbers -->
                    <xsl:if test="$pages != ''">
                        <xsl:call-template name="parsePages">
                            <xsl:with-param name="pages" select="normalize-space($pages)"/>
                        </xsl:call-template>
                    </xsl:if>
                </org>
            </xsl:matching-substring>
        </xsl:analyze-string>
    </xsl:template>

    <!-- Template for person entries -->
    <xsl:template match="P">
        <xsl:variable name="text" select="normalize-space(.)"/>
        <xsl:variable name="currentNode" select="."/>
        <xsl:variable name="personId" select="generate-id($currentNode)"/>

        <!-- Extract page numbers: look for pattern after last sentence/description -->
        <!-- Page numbers are typically: space followed by digits, commas, spaces, ending with digits -->
        <xsl:variable name="pages" select="if (matches($text, '\.[\s\p{L}]*[\s,]*[\d,\s]+$'))
                                           then replace($text, '^.*?\.\s*[^\d]*?([\d,\s]+)$', '$1')
                                           else ''"/>

        <!-- Remove page numbers from text -->
        <xsl:variable name="textWithoutPages" select="if ($pages != '')
                                                       then replace($text, '(\..*?)([\d,\s]+)$', '$1')
                                                       else $text"/>

        <!-- Extract the name part: everything before the first ( with dates -->
        <!-- Look for patterns like (1870–1942) or (?–1942) or (1870–?) -->
        <xsl:variable name="namePartRaw" select="if (matches($textWithoutPages, '\([^\)]*\d\d\d\d[^\)]*\)'))
                                                  then replace($textWithoutPages, '^(.*?)\s*\([^\)]*\d\d\d\d[^\)]*\).*$', '$1')
                                                  else if (matches($textWithoutPages, '\(\?[–—-]'))
                                                  then replace($textWithoutPages, '^(.*?)\s*\(\?[–—-][^\)]*\).*$', '$1')
                                                  else $textWithoutPages"/>

        <!-- Parse person name and dates using regex -->
        <!-- First try to find and separate the (eig. ...) part if present -->
        <xsl:variable name="altNamePart" select="if (contains($namePartRaw, '(eig.'))
                                                  then replace($namePartRaw, '^.*?\(eig\.\s*([^)]+)\).*$', '$1')
                                                  else ''"/>

        <!-- Extract birth name (geb. ...) -->
        <xsl:variable name="birthNamePart" select="if (matches($namePartRaw, ',\s+geb\.\s+[A-ZÄÖÜ]'))
                                                    then replace($namePartRaw, '^.*?,\s+geb\.\s+([A-ZÄÖÜ][^\s,.(]+).*$', '$1')
                                                    else ''"/>

        <!-- Extract married name (verh. ...) -->
        <xsl:variable name="marriedNamePart" select="if (matches($namePartRaw, ',\s+verh\.\s+[A-ZÄÖÜ]'))
                                                      then replace($namePartRaw, '^.*?,\s+verh\.\s+([A-ZÄÖÜ][^\s,.(]+).*$', '$1')
                                                      else ''"/>

        <!-- Clean the name part by removing (eig. ...), geb., and verh. parts -->
        <xsl:variable name="namePart" select="normalize-space(
                                               replace(
                                               replace(
                                               replace($namePartRaw,
                                                       '\(eig\.[^)]+\)\s*', ''),
                                                       ',\s+geb\.\s+[A-ZÄÖÜ][^\s,.(]+', ''),
                                                       ',\s+verh\.\s+[A-ZÄÖÜ][^\s,.(]+', ''))"/>

        <!-- Extract dates part -->
        <xsl:variable name="dates" select="if (matches($textWithoutPages, '\([^\)]*\d\d\d\d[^\)]*\)'))
                                            then replace($textWithoutPages, '^.*?(\([^\)]*\d\d\d\d[^\)]*\)).*$', '$1')
                                            else if (matches($textWithoutPages, '\(\?[–—-][^\)]*\)'))
                                            then replace($textWithoutPages, '^.*?(\(\?[–—-][^\)]*\)).*$', '$1')
                                            else ''"/>

        <!-- Extract description: everything after dates and before page numbers -->
        <xsl:variable name="afterDates" select="if ($dates != '')
                                                 then replace($textWithoutPages, '^.*?\([^\)]*\d\d\d\d[^\)]*\)\.?\s*(.*)$', '$1')
                                                 else ''"/>
        <xsl:variable name="description" select="normalize-space($afterDates)"/>

        <!-- Only create person element if we have a name part with comma (surname, forename) -->
        <xsl:if test="contains($namePart, ',')">
            <person xmlns="http://www.tei-c.org/ns/1.0">
                <xsl:attribute name="xml:id">
                    <xsl:value-of select="concat('person_', $personId)"/>
                </xsl:attribute>

                <!-- Parse name -->
                <xsl:call-template name="parseName">
                    <xsl:with-param name="namepart" select="$namePart"/>
                    <xsl:with-param name="altName" select="$altNamePart"/>
                    <xsl:with-param name="birthName" select="$birthNamePart"/>
                    <xsl:with-param name="marriedName" select="$marriedNamePart"/>
                </xsl:call-template>

                <!-- Parse dates if present -->
                <xsl:if test="$dates != ''">
                    <xsl:call-template name="parseDates">
                        <xsl:with-param name="dates" select="$dates"/>
                    </xsl:call-template>
                </xsl:if>

                <!-- Add description as note -->
                <xsl:if test="$description != ''">
                    <note>
                        <xsl:value-of select="$description"/>
                    </note>
                </xsl:if>

                <!-- Add page numbers as biblScope -->
                <xsl:if test="$pages != ''">
                    <xsl:call-template name="parsePages">
                        <xsl:with-param name="pages" select="normalize-space($pages)"/>
                    </xsl:call-template>
                </xsl:if>
            </person>
        </xsl:if>
    </xsl:template>

    <!-- Template to parse name -->
    <xsl:template name="parseName">
        <xsl:param name="namepart"/>
        <xsl:param name="altName" select="''"/>
        <xsl:param name="birthName" select="''"/>
        <xsl:param name="marriedName" select="''"/>

        <!-- Output main name -->
        <persName xmlns="http://www.tei-c.org/ns/1.0">
            <xsl:call-template name="splitName">
                <xsl:with-param name="name" select="$namepart"/>
            </xsl:call-template>
        </persName>

        <!-- Output alternative name if present (eig.) -->
        <xsl:if test="$altName != ''">
            <persName xmlns="http://www.tei-c.org/ns/1.0" type="alt">
                <xsl:call-template name="splitName">
                    <xsl:with-param name="name" select="$altName"/>
                </xsl:call-template>
            </persName>
        </xsl:if>

        <!-- Output birth name if present (geb.) -->
        <xsl:if test="$birthName != ''">
            <persName xmlns="http://www.tei-c.org/ns/1.0" type="birth">
                <surname>
                    <xsl:value-of select="$birthName"/>
                </surname>
            </persName>
        </xsl:if>

        <!-- Output married name if present (verh.) -->
        <xsl:if test="$marriedName != ''">
            <persName xmlns="http://www.tei-c.org/ns/1.0" type="married">
                <surname>
                    <xsl:value-of select="$marriedName"/>
                </surname>
            </persName>
        </xsl:if>
    </xsl:template>

    <!-- Template to split surname and forename -->
    <xsl:template name="splitName">
        <xsl:param name="name"/>

        <xsl:analyze-string select="$name" regex="^([^,]+),\s*(.+)$">
            <xsl:matching-substring>
                <surname xmlns="http://www.tei-c.org/ns/1.0">
                    <xsl:value-of select="normalize-space(regex-group(1))"/>
                </surname>
                <xsl:variable name="forenamePart" select="normalize-space(regex-group(2))"/>
                <!-- Check if forename contains a reference (→) -->
                <xsl:choose>
                    <xsl:when test="contains($forenamePart, '→')">
                        <!-- Split at → and create ref element -->
                        <xsl:analyze-string select="$forenamePart" regex="^(.*?)→(.+)$">
                            <xsl:matching-substring>
                                <xsl:variable name="actualForename" select="normalize-space(regex-group(1))"/>
                                <xsl:variable name="refTarget" select="normalize-space(regex-group(2))"/>
                                <xsl:choose>
                                    <xsl:when test="$actualForename != ''">
                                        <forename xmlns="http://www.tei-c.org/ns/1.0">
                                            <xsl:value-of select="$actualForename"/>
                                        </forename>
                                    </xsl:when>
                                </xsl:choose>
                                <ref xmlns="http://www.tei-c.org/ns/1.0" type="see">
                                    <xsl:value-of select="$refTarget"/>
                                </ref>
                            </xsl:matching-substring>
                        </xsl:analyze-string>
                    </xsl:when>
                    <xsl:otherwise>
                        <forename xmlns="http://www.tei-c.org/ns/1.0">
                            <xsl:value-of select="$forenamePart"/>
                        </forename>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:matching-substring>
            <xsl:non-matching-substring>
                <name xmlns="http://www.tei-c.org/ns/1.0">
                    <xsl:value-of select="normalize-space($name)"/>
                </name>
            </xsl:non-matching-substring>
        </xsl:analyze-string>
    </xsl:template>

    <!-- Template to parse dates -->
    <xsl:template name="parseDates">
        <xsl:param name="dates"/>

        <!-- Remove brackets -->
        <xsl:variable name="datesClean" select="replace(replace($dates, '\(', ''), '\)', '')"/>

        <!-- Parse birth and death dates -->
        <xsl:analyze-string select="$datesClean" regex="^([^–—-]+?)[–—-]([^–—-]+)$">
            <xsl:matching-substring>
                <birth xmlns="http://www.tei-c.org/ns/1.0">
                    <xsl:variable name="birthYear" select="normalize-space(regex-group(1))"/>
                    <xsl:if test="matches($birthYear, '^\d\d\d\d$')">
                        <xsl:attribute name="when" select="$birthYear"/>
                    </xsl:if>
                    <xsl:value-of select="$birthYear"/>
                </birth>
                <death xmlns="http://www.tei-c.org/ns/1.0">
                    <xsl:variable name="deathYear" select="normalize-space(regex-group(2))"/>
                    <xsl:if test="matches($deathYear, '^\d\d\d\d$')">
                        <xsl:attribute name="when" select="$deathYear"/>
                    </xsl:if>
                    <xsl:value-of select="$deathYear"/>
                </death>
            </xsl:matching-substring>
            <xsl:non-matching-substring>
                <!-- Single date (birth or death only) -->
                <xsl:choose>
                    <xsl:when test="starts-with($datesClean, '†')">
                        <death xmlns="http://www.tei-c.org/ns/1.0">
                            <xsl:value-of select="normalize-space(substring-after($datesClean, '†'))"/>
                        </death>
                    </xsl:when>
                    <xsl:when test="starts-with($datesClean, '*')">
                        <birth xmlns="http://www.tei-c.org/ns/1.0">
                            <xsl:value-of select="normalize-space(substring-after($datesClean, '*'))"/>
                        </birth>
                    </xsl:when>
                    <xsl:otherwise>
                        <date xmlns="http://www.tei-c.org/ns/1.0">
                            <xsl:value-of select="normalize-space($datesClean)"/>
                        </date>
                    </xsl:otherwise>
                </xsl:choose>
            </xsl:non-matching-substring>
        </xsl:analyze-string>
    </xsl:template>

    <!-- Template to parse page numbers -->
    <xsl:template name="parsePages">
        <xsl:param name="pages"/>

        <!-- Split page numbers by comma and create biblScope elements -->
        <xsl:for-each select="tokenize($pages, ',')">
            <xsl:variable name="pageRange" select="normalize-space(.)"/>
            <xsl:if test="$pageRange != ''">
                <note xmlns="http://www.tei-c.org/ns/1.0" type="page">
                    <!-- Check if it's a page range (e.g., "12–15") or single page -->
                    <xsl:choose>
                        <xsl:when test="matches($pageRange, '^\d+[–—-]\d+$')">
                            <xsl:analyze-string select="$pageRange" regex="^(\d+)[–—-](\d+)$">
                                <xsl:matching-substring>
                                    <xsl:attribute name="from" select="regex-group(1)"/>
                                    <xsl:attribute name="to" select="regex-group(2)"/>
                                    <xsl:value-of select="$pageRange"/>
                                </xsl:matching-substring>
                            </xsl:analyze-string>
                        </xsl:when>
                        <xsl:when test="matches($pageRange, '^\d+$')">
                            <xsl:attribute name="n" select="$pageRange"/>
                            <xsl:value-of select="$pageRange"/>
                        </xsl:when>
                        <xsl:otherwise>
                            <xsl:value-of select="$pageRange"/>
                        </xsl:otherwise>
                    </xsl:choose>
                </note>
            </xsl:if>
        </xsl:for-each>
    </xsl:template>

</xsl:stylesheet>
