import pandas, yaml, base64,  os, numpy, re, unicodedata
from simple_salesforce import Salesforce, SalesforceLogin


def ligacao_salesforce(credenciais_a_utilizar='prod'):
    # Guardar credenciais
    file_credenciais = "sf.yml"

    parent_dir = os.path.abspath(os.path.dirname(__file__))
    credenciais = yaml.safe_load(open(os.path.join(parent_dir, file_credenciais)))

    cred = credenciais[credenciais_a_utilizar].split(';')
    username = base64.b64decode(cred[0]).decode("utf8")
    password = base64.b64decode(cred[1]).decode("utf8")
    token = base64.b64decode(cred[2]).decode("utf8")

    # Criar sessão
    if credenciais_a_utilizar == 'prod_ricardo':
        session_id, instance = SalesforceLogin(username=username, password=password, organizationId=token)
    else:
        session_id, instance = SalesforceLogin(username=username, password=password, security_token=token)
    sf_ = Salesforce(instance=instance, session_id=session_id)

    return sf_


def query_salesforce(sf_, query):
    # Correr query
    try:
        tabela = sf_.query_all(query=query)
    except Exception as e:
        print(f"Erro no acesso a SF: {e}")
        return None

    # Tabela está vazia? Se sim
    table_size = tabela['totalSize']
    if table_size == 0:
        tabela = pandas.DataFrame()
    else:
        tabela = pandas.DataFrame(tabela['records']).drop(columns='attributes')

    return tabela


def obter_colunas_objeto(sf_, nome_objeto):
    colunas_objeto = []
    conteudo_objeto = sf_.__getattr__(nome_objeto).describe()['fields']
    for i in conteudo_objeto:
        colunas_objeto.append(i['name'])

    return colunas_objeto


def query_salesforce_select_all(sf_, objeto, where=''):
    colunas = obter_colunas_objeto(sf_=sf_, nome_objeto=objeto)
    colunas_str = ', '.join(colunas)
    if where == '' or where is None:
        query = f"select {colunas_str} from {objeto}"
    else:
        query = f"select {colunas_str} from {objeto} where {where}"

    tabela = query_salesforce(sf_=sf_, query=query)

    return tabela


def ids_ativos(sf):
    query = """
    select Id
    from Asset
    where Tipo__c = 'Posto de carregamento'
    and ProductFamily = 'Mobilidade Inteligente'
    and Country__c in ('pt_PT', 'es_ES')
    """

    df = query_salesforce(sf, query)

    if df is None or df.empty:
        return []

    return df["Id"].dropna().unique().astype(str).tolist()

    if pandas.isna(nome):
        return None

    nome = str(nome).strip()
    if "/" in nome:
        nome = nome.split("/")[-1]

    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = nome.lower()
    nome = re.sub(r"\s+", " ", nome).strip()

    return nome


def normalizar_distrito(nome):
    if pandas.isna(nome):
        return None

    nome = str(nome).strip()

    if "/" in nome:
        nome = nome.split("/")[-1]

    nome = unicodedata.normalize("NFKD", nome)
    nome = "".join(c for c in nome if not unicodedata.combining(c))
    nome = nome.lower()
    nome = re.sub(r"\s+", " ", nome).strip()

    return nome


def obter_ativos(sf_, lista):
    campos_asset = [
        'AccountId',
        'Address__c',
        'Asset_Manager__c',
        'AssetLevel',
        'City__c',
        'Contract_Serv_Value__c',
        'Contrato__c',
        'Cost_OM_Expected__c',
        'Country__c',
        'CPE__c',
        'CPE_Custom_RollUp__c',
        'CreatedById',
        'CurrencyIsoCode',
        'Custo_de_equipamentos__c',
        'Custo_de_Instalacao__c',
        'Description',
        'District__c',
        'Equipment__c',
        'Familia_de_Produtos__c',
        'Fornecido_Por__c',
        'Id',
        'InstallDate',
        'Installator_PSE__c',
        'LastModifiedById',
        'LastModifiedDate',
        'LocationId',
        'ManufactureDate',
        'Margin_after_construction__c',
        'Modelo_de_Negocio__c',
        'Name',
        'OM_PSE__c',
        'Operational_Assistant__c',
        'Origin__c',
        'Phase__c',
        'Price',
        'Product2Id',
        'ProductCode',
        'ProductDescription',
        'ProductFamily',
        'Project_Cost__c',
        'PurchaseDate',
        'Quantity',
        'Quote__c',
        'Realized_OM_Cost__c',
        'Realized_OM_value__c',
        'Station_Id__c',
        'Status',
        'Tipo__c',
        'UsageEndDate',
        'Zip_Code__c'
    ]

    colunas_asset = obter_colunas_objeto(sf_, 'Asset')
    campos_validos = [campo for campo in campos_asset if campo in colunas_asset]
    campos_validos = list(dict.fromkeys(campos_validos))
    campos_query = ', '.join(campos_validos)
    
    query = f"""
    select {campos_query}
    from Asset
    where Tipo__c = 'Posto de carregamento'
    and ProductFamily = 'Mobilidade Inteligente'
    and Country__c in ('pt_PT', 'es_ES')
    """

    ativos = query_salesforce(sf_, query)

    if ativos is None or ativos.empty:
        return pandas.DataFrame()

    if 'Id' in ativos.columns:
        ativos['salesforce_id'] = ativos['Id']

    if 'District__c' in ativos.columns:

        lista_distrito_id = (ativos['District__c'].dropna().astype(str).unique().tolist())

        if lista_distrito_id:
            lista_distrito_id_str = "'" + "', '".join(lista_distrito_id) + "'"
            
            query_distrito = f"""
            select Id, Name
            from Distrito__c
            where Id in ({lista_distrito_id_str})
            """

            aux_distrito = query_salesforce(sf_, query_distrito)

            if aux_distrito is not None and not aux_distrito.empty:
                aux_distrito = (aux_distrito[['Id', 'Name']].drop_duplicates(subset=['Id']).rename(columns={'Id': 'District__c', 'Name': 'District_Name'}))
                ativos = pandas.merge(ativos, aux_distrito, on='District__c',how='left')

    if 'District_Name' not in ativos.columns:
        ativos['District_Name'] = 'NA'

    ativos['District_Name'] = ativos['District_Name'].fillna('NA')

    mapa_lotes = {
        # Portugal
        'viana do castelo': 1,
        'braga': 1,
        'vila real': 2,
        'braganca': 2,
        'porto': 2,
        'aveiro': 3,
        'viseu': 3,
        'guarda': 3,
        'coimbra': 4,
        'castelo branco': 4,
        'leiria': 5,
        'santarem': 6,
        'portalegre': 6,
        'evora': 6,
        'lisboa': 7,
        'setubal': 8,
        'beja': 9,
        'faro': 9,
        'ilha da madeira': 10,
        'ilha de porto santo': 10,
        'ilha de santa maria': 10,
        'ilha de sao miguel': 10,
        'ilha terceira': 10,
        'ilha de sao jorge': 10,
        'ilha do pico': 10,
        'ilha do faial': 10,
        'ilha da graciosa': 10,
        'ilha das flores': 10,
        'ilha do corvo': 10,

        # Spain
        'a coruna': 101,
        'coruna': 101,
        'acoruna': 101,
        'lugo': 101,
        'ourense': 102,
        'pontevedra': 102,
        'asturias': 103,
        'cantabria': 103,
        'leon': 104,
        'palencia': 104,
        'burgos': 104,
        'vizcaya': 105,
        'guipuzcoa': 105,
        'alava': 105,
        'araba': 105, 
        'araba alava': 105,
        'navarra': 105,
        'la rioja': 105,
        'huesca': 106,
        'lleida': 106,
        'girona': 107,
        'barcelona': 107,
        'tarragona': 107,
        'zaragoza': 108,
        'albacete': 108,
        'soria': 108,
        'segovia': 108,
        'salamanca': 109,
        'avila': 109,
        'valladolid': 109,
        'madrid': 110,
        'guadalajara': 110,
        'cuenca': 110,
        'teruel': 110,
        'zamora': 111,
        'toledo': 111,
        'ciudad real': 111,
        'badajoz': 112,
        'caceres': 112,
        'cordoba': 112,
        'jaen': 112,
        'huelva': 112,
        'sevilla': 113,
        'granada': 113,
        'almeria': 113,
        'cadiz': 114,
        'malaga': 114,
        'castellon': 115,
        'castello': 115,
        'castello de la plana': 115,
        'valencia': 115,
        'alicante': 116,
        'murcia': 116,
        'santa cruz de tenerife': 117,
        'tenerife': 117,
        'palmas, las': 118,
        'las palmas': 118,
        'las palmas de gran canaria': 118,
        'illes balears': 119,
        'baleares': 119,
        'gipuzkoa': 105,
        'bizkaia': 105,
        'alacant': 116,
        'castello': 115,
        'coruna, a': 101,
        'rioja, la': 105,
        'pais basco': 105,
    }

    ativos['District_Normalizado'] = ativos['District_Name'].apply(normalizar_distrito)
    ativos['Lote'] = (ativos['District_Normalizado'].map(mapa_lotes).astype("Int64"))

    colunas_pse = [coluna for coluna in ['Installator_PSE__c', 'OM_PSE__c']if coluna in ativos.columns]

    if colunas_pse:
        tabela_accounts = pandas.concat([ativos[[coluna]].rename(columns={coluna: 'Id'}) for coluna in colunas_pse], ignore_index=True).dropna(subset=['Id'])
        lista_accounts = tabela_accounts['Id'].dropna().unique().tolist()

        if lista_accounts:
            lista_accounts_str = "'" + "', '".join(lista_accounts) + "'"

            query_accounts = f"""
            select Id, Name
            from Account
            where Id in ({lista_accounts_str})
            """

            accounts = query_salesforce(sf_, query_accounts)

            if accounts is not None and not accounts.empty:
                accounts = accounts[['Id', 'Name']].drop_duplicates(subset=['Id'])

                if 'Installator_PSE__c' in ativos.columns:
                    accounts_inst = accounts.rename(columns={
                        'Id': 'Installator_PSE__c',
                        'Name': 'Installator_PSE_Name'
                    })

                    ativos = pandas.merge(
                        left=ativos,
                        right=accounts_inst,
                        on='Installator_PSE__c',
                        how='left'
                    )

                if 'OM_PSE__c' in ativos.columns:
                    accounts_om = accounts.rename(columns={
                        'Id': 'OM_PSE__c',
                        'Name': 'OM_PSE_Name'
                    })

                    ativos = pandas.merge(
                        left=ativos,
                        right=accounts_om,
                        on='OM_PSE__c',
                        how='left'
                    )

    if 'Installator_PSE_Name' not in ativos.columns:
        ativos['Installator_PSE_Name'] = 'NA'

    if 'OM_PSE_Name' not in ativos.columns:
        ativos['OM_PSE_Name'] = 'NA'

    ativos['Installator_PSE_Name'] = ativos['Installator_PSE_Name'].fillna('NA')
    ativos['OM_PSE_Name'] = ativos['OM_PSE_Name'].fillna('NA')

    if 'Asset_Manager__c' in ativos.columns:
        lista_users = ativos.dropna(subset=['Asset_Manager__c'])['Asset_Manager__c'].unique().tolist()

        if lista_users:
            lista_users_str = "'" + "', '".join(lista_users) + "'"

            query_users = f"""
            select Id, Name
            from User
            where Id in ({lista_users_str})
            """

            tabela_users = query_salesforce(sf_, query_users)

            if tabela_users is not None and not tabela_users.empty:
                tabela_users = tabela_users[['Id', 'Name']].drop_duplicates(subset=['Id'])

                tabela_users = tabela_users.rename(columns={
                    'Id': 'Asset_Manager__c',
                    'Name': 'Asset_Manager_Name'
                })

                ativos = pandas.merge(
                    left=ativos,
                    right=tabela_users,
                    on='Asset_Manager__c',
                    how='left'
                )

    if 'Asset_Manager_Name' not in ativos.columns:
        ativos['Asset_Manager_Name'] = 'NA'

    ativos['Asset_Manager_Name'] = ativos['Asset_Manager_Name'].fillna('NA')

    return ativos.reset_index(drop=True)


def obter_eventos(sf_, lista, periodo=None, meio=None, estado=None, desde=None):
    if meio is None:
        meio = []

    if estado is None:
        estado = []

    campos_case = [
        'Asset_Type__c',
        'AssetId',
        'Case_Reference_ID__c',
        'CaseNumber',
        'Closed_Date__c',
        'ClosedDate',
        'Create_Date__c',
        'CreatedById',
        'CreatedDate',
        'Custo__c',
        'Data_de_Inicio_da_Analise__c',
        'Data_de_Inicio_da_Resolucao__c',
        'Data_de_Inicio_de_Espera_por_Feedback__c',
        'Data_de_Intervencao__c',
        'Descricao_da_Solucao__c',
        'Descricao_do_Problema__c',
        'External_Service_Provider__c',
        'Id',
        'Incident_Reason__c',
        'Incident_type__c',
        'Is_Case_Owner__c',
        'Last_Operator__c',
        'LastModifiedById',
        'LastModifiedDate',
        'Opened_Date__c',
        'Origin',
        'OwnerId',
        'Priority',
        'RecordTypeId',
        'Reportado_por__c',
        'Sale_Value__c',
        'Solution_B2B__c',
        'Status',
        'Subject',
        'Symptom__c',
        'Tipo_de_Resolucao__c',
        'Type'
    ]

    colunas_case = obter_colunas_objeto(sf_, 'Case')
    campos_validos = [campo for campo in campos_case if campo in colunas_case]
    campos_validos = list(dict.fromkeys(campos_validos))
    campos_query = ', '.join(campos_validos)

    tabela = pandas.DataFrame()
    i = 0
    step = 25

    while i < len(lista):
        sublista = "'" + "', '".join(lista[i:i + step]) + "'"

        query = f"""
        select {campos_query}
        from Case
        where AssetId in ({sublista})
        """

        if desde is not None and 'LastModifiedDate' in campos_validos:
            query += f" and LastModifiedDate >= {desde}"

        if len(meio) > 0 and 'Origin' in campos_validos:
            query += f""" and Origin in ({"'" + "', '".join(meio) + "'"})"""

        if len(estado) > 0 and 'Status' in campos_validos:
            query += f""" and Status in ({"'" + "', '".join(estado) + "'"})"""

        aux = query_salesforce(sf_, query)

        if aux is not None and not aux.empty:
            tabela = pandas.concat([tabela, aux], ignore_index=True)

        i += step

    if tabela.empty:
        return tabela.reset_index(drop=True)

    if periodo is not None and 'Create_Date__c' in tabela.columns:
        inicio, final = periodo
        datas = pandas.to_datetime(tabela['Create_Date__c'], errors='coerce').dt.date
        tabela = tabela[(datas >= inicio) & (datas <= final)]

    if tabela.empty:
        return tabela.reset_index(drop=True)

    if 'Id' in tabela.columns:
        tabela['case_id'] = tabela['Id']

    if 'AssetId' in tabela.columns:
        tabela['salesforce_id'] = tabela['AssetId']

    if 'RecordTypeId' in tabela.columns:
        lista_rt = tabela.dropna(subset=['RecordTypeId'])['RecordTypeId'].unique().tolist()

        if lista_rt:
            lista_rt_str = "'" + "', '".join(lista_rt) + "'"

            query_rt = f"""
            select Id, Name
            from RecordType
            where Id in ({lista_rt_str})
            """

            rt = query_salesforce(sf_, query_rt)

            if rt is not None and not rt.empty:
                rt = rt[['Id', 'Name']].drop_duplicates(subset=['Id'])
                rt = rt.rename(columns={
                    'Id': 'RecordTypeId',
                    'Name': 'tipo_solicitacao'
                })

                tabela = pandas.merge(
                    left=tabela,
                    right=rt,
                    on='RecordTypeId',
                    how='left'
                )

        if 'tipo_solicitacao' in tabela.columns:
            tabela = tabela[tabela['tipo_solicitacao'] == 'Evento']

    if tabela.empty:
        return tabela.reset_index(drop=True)

    if 'External_Service_Provider__c' in tabela.columns:
        lista_pse = tabela.dropna(subset=['External_Service_Provider__c'])['External_Service_Provider__c'].unique().tolist()

        if lista_pse:
            lista_pse_str = "'" + "', '".join(lista_pse) + "'"

            query_pse = f"""
            select Id, Name
            from Account
            where Id in ({lista_pse_str})
            """

            pse = query_salesforce(sf_, query_pse)

            if pse is not None and not pse.empty:
                pse = pse[['Id', 'Name']].drop_duplicates(subset=['Id'])
                pse = pse.rename(columns={
                    'Id': 'External_Service_Provider__c',
                    'Name': 'pse'
                })

                tabela = pandas.merge(
                    left=tabela,
                    right=pse,
                    on='External_Service_Provider__c',
                    how='left'
                )

    if 'pse' not in tabela.columns:
        tabela['pse'] = 'NA'

    tabela['pse'] = tabela['pse'].fillna('NA')

    if 'Symptom__c' in tabela.columns:
        lista_sintoma = tabela.dropna(subset=['Symptom__c'])['Symptom__c'].unique().tolist()

        if lista_sintoma:
            lista_sintoma_str = "'" + "', '".join(lista_sintoma) + "'"

            query_sintoma = f"""
            select Id, Name
            from Symptom_Catalog__c
            where Id in ({lista_sintoma_str})
            """

            sintoma = query_salesforce(sf_, query_sintoma)

            if sintoma is not None and not sintoma.empty:
                sintoma = sintoma[['Id', 'Name']].drop_duplicates(subset=['Id'])
                sintoma = sintoma.rename(columns={
                    'Id': 'Symptom__c',
                    'Name': 'sintoma'
                })

                tabela = pandas.merge(
                    left=tabela,
                    right=sintoma,
                    on='Symptom__c',
                    how='left'
                )

    if 'sintoma' not in tabela.columns:
        tabela['sintoma'] = ''

    tabela['sintoma'] = tabela['sintoma'].fillna('')

    if 'OwnerId' in tabela.columns:
        lista_owner = tabela.dropna(subset=['OwnerId'])['OwnerId'].unique().tolist()

        if lista_owner:
            lista_owner_str = "'" + "', '".join(lista_owner) + "'"

            query_users = f"""
            select Id, Name
            from User
            where Id in ({lista_owner_str})
            """

            users = query_salesforce(sf_, query_users)

            query_groups = f"""
            select Id, Name
            from Group
            where Id in ({lista_owner_str})
            """

            groups = query_salesforce(sf_, query_groups)

            owners = pandas.DataFrame()

            if users is not None and not users.empty:
                users = users[['Id', 'Name']].drop_duplicates(subset=['Id'])
                users = users.rename(columns={
                    'Id': 'OwnerId',
                    'Name': 'Case_Owner'
                })
                owners = pandas.concat([owners, users], ignore_index=True)

            if groups is not None and not groups.empty:
                groups = groups[['Id', 'Name']].drop_duplicates(subset=['Id'])
                groups = groups.rename(columns={
                    'Id': 'OwnerId',
                    'Name': 'Case_Owner'
                })
                owners = pandas.concat([owners, groups], ignore_index=True)

            if not owners.empty:
                owners = owners.drop_duplicates(subset=['OwnerId'], keep='first')

                tabela = pandas.merge(
                    left=tabela,
                    right=owners,
                    on='OwnerId',
                    how='left'
                )

    if 'Case_Owner' not in tabela.columns:
        tabela['Case_Owner'] = 'NA'

    tabela['Case_Owner'] = tabela['Case_Owner'].fillna('NA')

    return tabela.reset_index(drop=True)


def obter_po(sf_, lista, periodo=None, meio=None, estado=None, desde=None):
    if meio is None:
        meio = []

    if estado is None:
        estado = []

    campos_case = [
        'AssetId',
        'Id',
        'CaseNumber',
        'Status',
        'Type',
        'Origin',
        'Create_Date__c',
        'Closed_Date__c',
        'ClosedDate',
        'Resolution_Date__c',
        'CreatedDate',
        'CreatedById',
        'LastModifiedDate',
        'LastModifiedById',
        'OwnerId',
        'Priority',
        'Subject',
        'Description',
        'Tipo_de_Pedido_de_Operacao__c',
        'External_Service_Provider__c',
        'Custo__c',
        'Valor__c',
        'Descricao_PO__c',
        'Planeamento_de_Intervencao__c',
        'Data_de_Agendamento__c',
        'Data_de_Intervencao__c',
        'Intervention_Duration__c',
        'Teve_Intervencao_no_Local__c',
        'Last_Operator__c',
        'Reatribuido__c',
        'Format_Status__c',
        'Status_Pendente__c',
        'Data_Modificacao_Estado__c',
        'AccountId',
        'ContactId',
        'Technical_Contact_PSE__c',
        'Asset_Type__c',
        'Case_Reference_ID__c',
        'ParentId',
        'Solution_B2B__c',
        'Descricao_da_Solucao__c',
        'Descricao_do_Problema__c'
    ]

    colunas_case = obter_colunas_objeto(sf_, 'Case')
    campos_validos = [campo for campo in campos_case if campo in colunas_case]
    campos_validos = list(dict.fromkeys(campos_validos))
    campos_query = ', '.join(campos_validos)

    tabela = pandas.DataFrame()
    i = 0
    step = 25

    while i < len(lista):
        sublista = "'" + "', '".join(lista[i:i + step]) + "'"

        query = f"""
        select {campos_query}
        from Case
        where AssetId in ({sublista})
        and Type = 'PEDIDO_OPERACAO'
        """

        if periodo is not None and 'Create_Date__c' in campos_validos:
            inicio, final = periodo
            query += f" and Create_Date__c >= {inicio.isoformat()}"
            query += f" and Create_Date__c <= {final.isoformat()}"

        if desde is not None and 'LastModifiedDate' in campos_validos:
            query += f" and LastModifiedDate >= {desde}"

        if len(meio) > 0 and 'Origin' in campos_validos:
            query += f""" and Origin in ({"'" + "', '".join(meio) + "'"})"""

        if len(estado) > 0 and 'Status' in campos_validos:
            query += f""" and Status in ({"'" + "', '".join(estado) + "'"})"""

        aux = query_salesforce(sf_, query)

        if aux is not None and not aux.empty:
            tabela = pandas.concat([tabela, aux], ignore_index=True)

        i += step

    if tabela.empty:
        return tabela.reset_index(drop=True)

    if periodo is not None and 'Create_Date__c' in tabela.columns:
        inicio, final = periodo
        datas = pandas.to_datetime(tabela['Create_Date__c'], errors='coerce').dt.date
        tabela = tabela[(datas >= inicio) & (datas <= final)]

    if tabela.empty:
        return tabela.reset_index(drop=True)

    if 'Id' in tabela.columns:
        tabela['case_id'] = tabela['Id']

    if 'AssetId' in tabela.columns:
        tabela['salesforce_id'] = tabela['AssetId']

    if 'External_Service_Provider__c' in tabela.columns:
        lista_pse = tabela.dropna(subset=['External_Service_Provider__c'])['External_Service_Provider__c'].unique().tolist()

        if lista_pse:
            lista_pse_str = "'" + "', '".join(lista_pse) + "'"

            query_pse = f"""
            select Id, Name
            from Account
            where Id in ({lista_pse_str})
            """

            pse = query_salesforce(sf_, query_pse)

            if pse is not None and not pse.empty:
                pse = pse[['Id', 'Name']].drop_duplicates(subset=['Id'])

                pse = pse.rename(columns={
                    'Id': 'External_Service_Provider__c',
                    'Name': 'pse'
                })

                tabela = pandas.merge(
                    left=tabela,
                    right=pse,
                    on='External_Service_Provider__c',
                    how='left'
                )

    if 'pse' not in tabela.columns:
        tabela['pse'] = 'NA'

    tabela['pse'] = tabela['pse'].fillna('NA')

    if 'OwnerId' in tabela.columns:
        lista_owner = tabela.dropna(subset=['OwnerId'])['OwnerId'].unique().tolist()

        if lista_owner:
            lista_owner_str = "'" + "', '".join(lista_owner) + "'"

            query_users = f"""
            select Id, Name
            from User
            where Id in ({lista_owner_str})
            """

            users = query_salesforce(sf_, query_users)

            query_groups = f"""
            select Id, Name
            from Group
            where Id in ({lista_owner_str})
            """

            groups = query_salesforce(sf_, query_groups)

            owners = pandas.DataFrame()

            if users is not None and not users.empty:
                users = (
                    users[['Id', 'Name']]
                    .drop_duplicates(subset=['Id'])
                    .rename(columns={
                        'Id': 'OwnerId',
                        'Name': 'PO_Owner'
                    })
                )

                owners = pandas.concat([owners, users], ignore_index=True)

            if groups is not None and not groups.empty:
                groups = (
                    groups[['Id', 'Name']]
                    .drop_duplicates(subset=['Id'])
                    .rename(columns={
                        'Id': 'OwnerId',
                        'Name': 'PO_Owner'
                    })
                )

                owners = pandas.concat([owners, groups], ignore_index=True)

            if not owners.empty:
                owners = owners.drop_duplicates(subset=['OwnerId'], keep='first')

                tabela = pandas.merge(
                    left=tabela,
                    right=owners,
                    on='OwnerId',
                    how='left'
                )

    if 'PO_Owner' not in tabela.columns:
        tabela['PO_Owner'] = 'NA'

    tabela['PO_Owner'] = tabela['PO_Owner'].fillna('NA')

    if 'Technical_Contact_PSE__c' in tabela.columns:

        lista_contactos = (
            tabela['Technical_Contact_PSE__c']
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        if lista_contactos:

            lista_contactos_str = "'" + "', '".join(lista_contactos) + "'"

            query_contactos = f"""
            select Salesforce_ID__c, Aux_integration_Smile__c
            from Contact
            where Salesforce_ID__c in ({lista_contactos_str})
            """

            contactos = query_salesforce(sf_, query_contactos)

            if contactos is not None and not contactos.empty:

                contactos = (
                    contactos[['Salesforce_ID__c', 'Aux_integration_Smile__c']]
                    .drop_duplicates(subset=['Salesforce_ID__c'])
                    .rename(columns={
                        'Salesforce_ID__c': 'Technical_Contact_PSE__c',
                        'Aux_integration_Smile__c': 'Technical_Contact_PSE_Name'
                    })
                )

                tabela = pandas.merge(
                    left=tabela,
                    right=contactos,
                    on='Technical_Contact_PSE__c',
                    how='left'
                )

    if 'Technical_Contact_PSE_Name' not in tabela.columns:
        tabela['Technical_Contact_PSE_Name'] = 'NA'

    tabela['Technical_Contact_PSE_Name'] = tabela['Technical_Contact_PSE_Name'].fillna('NA')

    tabela = tabela.rename(columns={"CreatedDate": "WO_CreatedDate"})
        
    if (
        'Status' in tabela.columns
        and 'PO_Owner' in tabela.columns
        and 'Technical_Contact_PSE_Name' in tabela.columns
    ):

        estados_fechados = [
            'FECHADO',
            'RESOLVIDO',
            'CANCELADO'
        ]

        tabela['PSE_O&M'] = numpy.where(
            (~tabela['Status'].isin(estados_fechados))
            &
            (tabela['Technical_Contact_PSE_Name'] != 'NA'),
            tabela['Technical_Contact_PSE_Name'],
            tabela['PO_Owner']
        )
        
    return tabela.reset_index(drop=True)


def construir_task_owner(eventos, pedidos_operacao):
    
    if eventos is None or eventos.empty:
        return eventos

    eventos = eventos.copy()

    if pedidos_operacao is not None and not pedidos_operacao.empty:

        wo = pedidos_operacao.copy()

        wo["WO_CreatedDate"] = pandas.to_datetime(
            wo["WO_CreatedDate"],
            utc=True,
            errors="coerce"
        )

        wo = (
            wo.sort_values("WO_CreatedDate", ascending=False)
              .drop_duplicates(subset=["ParentId"], keep="first")
        )

        wo = wo[
            [
                "ParentId",
                "PSE_O&M",
                "WO_CreatedDate"
            ]
        ].rename(columns={
            "ParentId": "case_id"
        })

        eventos = eventos.merge(
            wo,
            on="case_id",
            how="left"
        )

    else:

        eventos["PSE_O&M"] = pandas.NA
        eventos["WO_CreatedDate"] = pandas.NaT

    estados_case_owner = [
        "POR_INICIAR",
        "EM_ANALISE",
        "AGUARDA_FEEDBACK",
        "FECHADO",
        "CANCELADO"
    ]

    eventos["Task Owner"] = numpy.where(
        eventos["Status"].isin(estados_case_owner),
        eventos["Case_Owner"],
        eventos["PSE_O&M"]
    )

    eventos["Task Owner Attribution Date"] = pandas.to_datetime(
        eventos["CreatedDate"],
        utc=True,
        errors="coerce"
    )

    mask = ~eventos["Status"].isin(estados_case_owner)

    eventos.loc[
        mask,
        "Task Owner Attribution Date"
    ] = eventos.loc[
        mask,
        "WO_CreatedDate"
    ]

    hoje = pandas.Timestamp.now(tz="UTC").normalize()

    data_fim = pandas.to_datetime(
        eventos["ClosedDate"],
        utc=True,
        errors="coerce"
    ).fillna(hoje)

    eventos["Days Task Owner"] = (
        data_fim.dt.normalize()
        - eventos["Task Owner Attribution Date"].dt.normalize()
    ).dt.days

    eventos["Days Task Owner"] = (
        eventos["Days Task Owner"]
        .fillna(0)
        .astype(int)
    )

    return eventos


def obter_sintoma_eventos_pai(sf_, lista_solicitacoes):
    i = 0
    step = 50
    solicitacoes_pai = pandas.DataFrame()

    while i < len(lista_solicitacoes):
        sublista = "'" + "', '".join(lista_solicitacoes[i:i + step]) + "'"

        query = f"""
        select Id, ParentId
        from Case
        where Id in ({sublista})
        """

        aux = query_salesforce(sf_, query)

        if aux is not None and not aux.empty:
            solicitacoes_pai = pandas.concat([solicitacoes_pai, aux], ignore_index=True)

        i += step

    if solicitacoes_pai.empty:
        return pandas.DataFrame()

    solicitacoes_pai['case_id'] = solicitacoes_pai['Id']
    solicitacoes_pai['parent_case_id'] = solicitacoes_pai['ParentId']

    lista_solicitacoes_pai = solicitacoes_pai.dropna(subset=['ParentId'])['ParentId'].unique().tolist()

    if not lista_solicitacoes_pai:
        solicitacoes_pai['symptom_name'] = ''
        solicitacoes_pai['incident_reason_name'] = ''
        solicitacoes_pai['macro_symptom'] = 'outro'
        return solicitacoes_pai.reset_index(drop=True)

    i = 0
    info_solicitacoes_pai = pandas.DataFrame()

    while i < len(lista_solicitacoes_pai):
        sublista = "'" + "', '".join(lista_solicitacoes_pai[i:i + step]) + "'"

        query = f"""
        select Id, Symptom__c, Incident_Reason__c
        from Case
        where Id in ({sublista})
        """

        aux = query_salesforce(sf_, query)

        if aux is not None and not aux.empty:
            info_solicitacoes_pai = pandas.concat([info_solicitacoes_pai, aux], ignore_index=True)

        i += step

    if info_solicitacoes_pai.empty:
        return solicitacoes_pai.reset_index(drop=True)

    info_solicitacoes_pai['parent_case_id'] = info_solicitacoes_pai['Id']

    if 'Symptom__c' in info_solicitacoes_pai.columns:
        lista_sintoma = info_solicitacoes_pai.dropna(subset=['Symptom__c'])['Symptom__c'].unique().tolist()

        if lista_sintoma:
            lista_sintoma_str = "'" + "', '".join(lista_sintoma) + "'"

            sintoma = query_salesforce(
                sf_,
                f"""
                select Id, Name
                from Symptom_Catalog__c
                where Id in ({lista_sintoma_str})
                """
            )

            if sintoma is not None and not sintoma.empty:
                sintoma = sintoma[['Id', 'Name']].copy()
                sintoma['symptom_name'] = sintoma['Name']

                info_solicitacoes_pai = pandas.merge(
                    left=info_solicitacoes_pai,
                    right=sintoma[['Id', 'symptom_name']],
                    left_on='Symptom__c',
                    right_on='Id',
                    how='left'
                )

                info_solicitacoes_pai = info_solicitacoes_pai.drop(columns=['Id_y'])
                info_solicitacoes_pai = info_solicitacoes_pai.rename(columns={'Id_x': 'Id'})

    if 'Incident_Reason__c' in info_solicitacoes_pai.columns:
        lista_motivo = info_solicitacoes_pai.dropna(subset=['Incident_Reason__c'])['Incident_Reason__c'].unique().tolist()

        if lista_motivo:
            lista_motivo_str = "'" + "', '".join(lista_motivo) + "'"

            motivo = query_salesforce(
                sf_,
                f"""
                select Id, Name
                from Incident_Catalog__c
                where Id in ({lista_motivo_str})
                """
            )

            if motivo is not None and not motivo.empty:
                motivo = motivo[['Id', 'Name']].copy()
                motivo['incident_reason_name'] = motivo['Name']

                info_solicitacoes_pai = pandas.merge(
                    left=info_solicitacoes_pai,
                    right=motivo[['Id', 'incident_reason_name']],
                    left_on='Incident_Reason__c',
                    right_on='Id',
                    how='left'
                )

                info_solicitacoes_pai = info_solicitacoes_pai.drop(columns=['Id_y'])
                info_solicitacoes_pai = info_solicitacoes_pai.rename(columns={'Id_x': 'Id'})

    tabela = pandas.merge(
        left=solicitacoes_pai,
        right=info_solicitacoes_pai,
        on='parent_case_id',
        how='left',
        suffixes=('', '_parent')
    )

    if 'symptom_name' not in tabela.columns:
        tabela['symptom_name'] = ''

    tabela['symptom_name'] = tabela['symptom_name'].fillna('')

    texto = tabela['symptom_name'].str.lower()

    tabela['macro_symptom'] = numpy.select(
        condlist=[
            texto.str.contains('cabo preso'),
            texto.str.contains('danificad'),
            texto.str.contains('desligado') | texto.str.contains('fora de serviço') | texto.apply(lambda x: bool(re.compile(r'out(\D)?of(\D)?order').search(x))),
            texto.str.contains('não inicia') | texto.str.contains('carregamento'),
            texto.str.contains('não rearma'),
            texto.str.contains('offline') | texto.str.contains('sem comunica')
        ],
        choicelist=[
            'cabo preso',
            'equipamento danificado',
            'fora de serviço',
            'problema no carregamento',
            'disjuntor não rearma',
            'offline'
        ],
        default='outro'
    )

    return tabela.reset_index(drop=True)

    
def obter_empresa(sf_, lista):
    i = 0
    step = 50
    ativo_empresa = pandas.DataFrame()

    while i < len(lista):
        sublista = "'" + "', '".join(lista[i:i + step]) + "'"

        query = f"""
        select Id, AccountId
        from Asset
        where Id in ({sublista})
        """

        aux = query_salesforce(sf_, query)

        if aux is not None and not aux.empty:
            ativo_empresa = pandas.concat([ativo_empresa, aux], ignore_index=True)

        i += step

    if ativo_empresa.empty:
        return pandas.DataFrame()

    ativo_empresa['salesforce_id'] = ativo_empresa['Id']
    ativo_empresa['empresa_id'] = ativo_empresa['AccountId']

    lista_empresa = ativo_empresa.dropna(subset=['AccountId'])['AccountId'].unique().tolist()

    if not lista_empresa:
        return ativo_empresa.reset_index(drop=True)

    campos_account = [
        'Id',
        'Name',
        'NIPC__c',
        'Phone',
        'Email__c',
        'Segment__c',
        'CAE__c',
        'OwnerId',
        'Gestor_de_Servicos__c',
        'Aux_Nome_Concelho__c',
        'Aux_Concelho__c',
        'County__c',
        'Concelho__c',
        'Distrito__c',
        'District__c',
        'Address__c',
        'Postal_Code__c',
        'LastModifiedDate'
    ]

    colunas_account = obter_colunas_objeto(sf_, 'Account')
    campos_validos = [campo for campo in campos_account if campo in colunas_account]
    campos_query = ', '.join(campos_validos)

    i = 0
    empresa = pandas.DataFrame()

    while i < len(lista_empresa):
        sublista = "'" + "', '".join(lista_empresa[i:i + step]) + "'"

        query = f"""
        select {campos_query}
        from Account
        where Id in ({sublista})
        """

        aux = query_salesforce(sf_, query)

        if aux is not None and not aux.empty:
            empresa = pandas.concat([empresa, aux], ignore_index=True)

        i += step

    if empresa.empty:
        return ativo_empresa.reset_index(drop=True)

    empresa['empresa_id'] = empresa['Id']
    empresa['nome_empresa'] = empresa['Name']

    if 'CAE__c' in empresa.columns:
        empresa['cae_id'] = empresa['CAE__c']

    tabela = pandas.merge(
        left=ativo_empresa,
        right=empresa,
        on='empresa_id',
        how='left',
        suffixes=('', '_account')
    )

    if 'cae_id' in tabela.columns:
        lista_cae = tabela.dropna(subset=['cae_id'])['cae_id'].unique().tolist()

        if lista_cae:
            lista_cae_str = "'" + "', '".join(lista_cae) + "'"

            cae = query_salesforce(
                sf_,
                f"""
                select Id, Name
                from CAE__c
                where Id in ({lista_cae_str})
                """
            )

            if cae is not None and not cae.empty:
                cae = cae[['Id', 'Name']].copy()
                cae['cae'] = cae['Name']

                tabela = pandas.merge(
                    left=tabela,
                    right=cae[['Id', 'cae']],
                    left_on='cae_id',
                    right_on='Id',
                    how='left'
                )

                tabela = tabela.drop(columns=['Id_y'])
                tabela = tabela.rename(columns={'Id_x': 'Id'})

    if 'cae' not in tabela.columns:
        tabela['cae'] = ''

    tabela['cae'] = tabela['cae'].fillna('')

    return tabela.reset_index(drop=True)


def obter_ct_eq_tomadas(sf_, lista, retirar_duplicados=True):
    campos_ct = [
        'Id',
        'OwnerId',
        'IsDeleted',
        'Name',
        'CurrencyIsoCode',
        'CreatedDate',
        'CreatedById',
        'LastModifiedDate',
        'LastModifiedById',
        'SystemModstamp',
        'Construction__c',
        'Product__c',
        'Gestao_de_Consumos__c',
        'Interconnection_Site__c',
        'Interconnection_Voltage_Level__c',
        'Installation_Type__c',
        'Mobi_E_Connection__c',
        'Technical_Observations__c',
        'Number_of_Charging_Stations__c',
        'Number_of_Equipment_Installed_PIEE__c',
        'Designacao_Local_Interligacao__c',
        'Nivel_Tensao__c',
        'TRE_OPC__c',
        'Localizacao__c',
        'Asset__c',
        'EV_Charge_Connection__c',
        'Source__c',
        'Responsibility_for_TRE__c',
        'Construction_Name__c',
        'Generate_Template__c',
        'Technical_Control_Template__c',
        'MOBI_E_DPC_Connection__c',
        'Quote__c',
        'Electric_Mobility_Type__c',
        'POD_Production__c',
    ]

    colunas_ct = obter_colunas_objeto(sf_, 'Technical_Control__c')
    campos_validos = [campo for campo in campos_ct if campo in colunas_ct]
    campos_query = ", ".join(campos_validos)
    ct = pandas.DataFrame()

    i = 0
    step = 50

    while i < len(lista):
        sublista = "'" + "', '".join(lista[i:i + step]) + "'"

        query = f"""
        SELECT {campos_query}
        FROM Technical_Control__c
        WHERE Asset__c IN ({sublista})
        """

        aux = query_salesforce(sf_, query)

        if aux is not None and not aux.empty:
            ct = pandas.concat([ct, aux], ignore_index=True)

        i += step

    if ct.empty:
        return (pandas.DataFrame(),pandas.DataFrame(),pandas.DataFrame())

    ct["ct_id"] = ct["Id"]
    ct["salesforce_id"] = ct["Asset__c"]
    ct["origem"] = (ct["Source__c"] if "Source__c" in ct.columns else None)

    if "Number_of_Charging_Stations__c" in ct.columns:
        ct["numero_postos_carregamento"] = (ct["Number_of_Charging_Stations__c"])
        
    ct_final = pandas.DataFrame()

    for salesforce_id in ct["salesforce_id"].dropna().unique():
        bloco = ct[ct["salesforce_id"] == salesforce_id].copy()

        if len(bloco) == 1:
            ct_final = pandas.concat([ct_final, bloco], ignore_index=True)
            continue

        bloco_ga = bloco[bloco["origem"] == "GA"].copy()

        if len(bloco_ga) == 1:
            ct_final = pandas.concat([ct_final, bloco_ga], ignore_index=True)
            continue

        candidato = (bloco_ga if len(bloco_ga) > 1 else bloco)
        candidato["ranking"] = (candidato.isnull().sum(axis=1))

        if "numero_postos_carregamento" in candidato.columns:
            candidato = candidato.sort_values(by=["ranking", "numero_postos_carregamento"],ascending=[True, False])

        else:
            candidato = candidato.sort_values(by="ranking")

        candidato = candidato.drop_duplicates(subset=["salesforce_id"], keep="first")
        candidato = candidato.drop(columns=["ranking"])
        ct_final = pandas.concat([ct_final, candidato], ignore_index=True)

    ct = ct_final.copy()

    if "Localizacao__c" in ct.columns:
        localizacao = pandas.json_normalize(ct["Localizacao__c"])
        ct = pandas.concat([ct.drop(columns=["Localizacao__c"]), localizacao],axis=1)

    if retirar_duplicados and not ct.empty:
        ct["ranking"] = (ct.isnull().sum(axis=1))
        ct = ct.sort_values(by="ranking")
        ct = ct.drop_duplicates(subset=["salesforce_id"], keep="first")
        ct = ct.drop(columns=["ranking"])

    lista_ct_id = (ct["ct_id"].dropna().unique().tolist())

    if not lista_ct_id:
        return (ct.reset_index(drop=True), pandas.DataFrame(), pandas.DataFrame())

    campos_eq = [
        'Id',
        'Name',
        'CurrencyIsoCode',
        'RecordTypeId',
        'CreatedDate',
        'CreatedById',
        'LastModifiedDate',
        'LastModifiedById',
        'SystemModstamp',
        'Controlo_Tecnico__c',
        'OtherBrand__c',
        'Equipment_Type__c',
        'Model__c',
        'Warranty_years__c',
        'Accessibility__c',
        'Card_Number__c',
        'GPRS_ICCID__c',
        'ID_Mobi_E__c',
        'Localization__c',
        'Number_of_Points__c',
        'Potencia_kW__c',
        'Serial_Number__c',
        'Observations__c',
        'Fixation_Type__c',
        'Location__Latitude__s',
        'Location__Longitude__s',
        'Location__c',
        'N_Plugs__c',
        'BrandModel__c',
        'Brand_and_Model_Name__c',
        'Material_Code__c',
        'Power_kW_matrix__c',
        'Warranty_years_Matrix__c',
        'Exist_Serial_Number__c'
    ]

    colunas_eq = obter_colunas_objeto(sf_, "Equipment__c")
    campos_validos = [campo for campo in campos_eq if campo in colunas_eq]
    campos_query = ", ".join(campos_validos)
    eq = pandas.DataFrame()

    i = 0

    while i < len(lista_ct_id):
        sublista = "'" + "', '".join(lista_ct_id[i:i + step]) + "'"

        query = f"""
        SELECT {campos_query}
        FROM Equipment__c
        WHERE Equipment_Type__c = 'Charging_Post'
        AND Controlo_Tecnico__c IN ({sublista})
        """

        aux = query_salesforce(sf_, query)

        if aux is not None and not aux.empty:
            eq = pandas.concat([eq, aux], ignore_index=True)

        i += step
        
        if eq.empty:
            return (ct.reset_index(drop=True), pandas.DataFrame(), pandas.DataFrame())

    eq["ct_id"] = eq["Controlo_Tecnico__c"]
    eq["eq_id"] = eq["Id"]

    if "Location__c" in eq.columns:
        def retirar_coordenadas(valor):
            if isinstance(valor, dict):
                return (valor.get("latitude"), valor.get("longitude"))

            return numpy.nan, numpy.nan

        eq[["latitude_aux", "longitude_aux"]] = (eq["Location__c"].apply(retirar_coordenadas).apply(pandas.Series))

        if "Location__Latitude__s" in eq.columns:
            eq["latitude"] = numpy.where(eq["Location__Latitude__s"].notnull(), eq["Location__Latitude__s"], eq["latitude_aux"])

        else:
            eq["latitude"] = eq["latitude_aux"]

        if "Location__Longitude__s" in eq.columns:
            eq["longitude"] = numpy.where(eq["Location__Longitude__s"].notnull(), eq["Location__Longitude__s"], eq["longitude_aux"])

        else:
            eq["longitude"] = eq["longitude_aux"]

        eq = eq.drop(columns=["latitude_aux", "longitude_aux"])

    eq = pandas.merge(left=ct, right=eq, on="ct_id", how="inner")

    if ("salesforce_id" in eq.columns and "ID_Mobi_E__c" in eq.columns):
        analise_eq_duplicados = (eq["salesforce_id"].value_counts().reset_index())
        analise_eq_duplicados.columns = ["salesforce_id", "contagem_postos"]
        analise_eq_duplicados = analise_eq_duplicados[analise_eq_duplicados["contagem_postos"] > 1]

        if not analise_eq_duplicados.empty:
            lista_ativos = (analise_eq_duplicados["salesforce_id"].unique().tolist())
            lista_ativos_str = ("'" + "', '".join(lista_ativos) + "'")
            
            tab_nome_ativos = query_salesforce(
                sf_,
                f"""
                SELECT
                    Id,
                    Name
                FROM Asset
                WHERE Id IN ({lista_ativos_str})
                """)

            if (tab_nome_ativos is not None and not tab_nome_ativos.empty):
                tab_nome_ativos["salesforce_id"] = (tab_nome_ativos["Id"])
                tab_nome_ativos["nome_ativo"] = (tab_nome_ativos["Name"])

                estrutura_id_posto_pt = re.compile(r"\w\w\w\w-\w\w\w-\d\d\d\d\d")
                estrutura_id_posto_es = re.compile(r"ES\*EDP\w\d\d\d\d\d(\*\d)?")

                def retirar_id_posto(valor):
                    if not isinstance(valor, str):
                        return None

                    match_pt = (estrutura_id_posto_pt.search(valor))
                    if match_pt:
                        return match_pt.group()

                    match_es = (estrutura_id_posto_es.search(valor))
                    if match_es:
                        return match_es.group()

                    return None

                tab_nome_ativos["id_posto_nome"] = (tab_nome_ativos["nome_ativo"].apply(retirar_id_posto))
                eq_corrigidos = pandas.DataFrame()

                for salesforce_id in lista_ativos:
                    bloco = eq[eq["salesforce_id"] == salesforce_id].copy()
                    ids_posto = (bloco["ID_Mobi_E__c"].dropna().unique().tolist())

                    if len(ids_posto) == 1:
                        eq_corrigidos = pandas.concat([eq_corrigidos,bloco.iloc[[0]]], ignore_index=True)
                        continue

                    id_posto = (tab_nome_ativos[tab_nome_ativos["salesforce_id"] == salesforce_id]["id_posto_nome"])

                    if id_posto.empty:
                        continue
                    
                    bloco_corrigido = bloco[bloco["ID_Mobi_E__c"] == id_posto.values[0]]

                    if not bloco_corrigido.empty:
                        eq_corrigidos = pandas.concat([eq_corrigidos,bloco_corrigido],ignore_index=True)

                eq = eq[~eq["salesforce_id"].isin(lista_ativos)]
                eq = pandas.concat([eq, eq_corrigidos], ignore_index=True)

    tomadas = pandas.DataFrame()
    lista_eq_id = (eq["eq_id"].dropna().unique().tolist())

    if not lista_eq_id:
        return (ct.reset_index(drop=True), eq.reset_index(drop=True), pandas.DataFrame())

    campos_plug = [
        'Equipment__c',
        'Id',
        'Name',
        'Plug_ID__c',
        'Point_ID__c',
        'Connector_Type__c',
        'Component_Type__c',
        'Current_Type__c',
        'Power_kW__c',
        'CreatedDate',
        'CreatedById',
        'LastModifiedDate',
        'LastModifiedById',
        'SystemModstamp'
    ]

    colunas_plug = obter_colunas_objeto(sf_,"Plug__c")
    campos_validos = [campo for campo in campos_plug if campo in colunas_plug]
    campos_query = ", ".join(campos_validos)

    i = 0

    while i < len(lista_eq_id):
        sublista = "'" + "', '".join(lista_eq_id[i:i + step]) + "'"

        query = f"""
        SELECT {campos_query}
        FROM Plug__c
        WHERE Equipment__c IN ({sublista})
        """

        aux = query_salesforce(sf_, query)

        if aux is not None and not aux.empty:
            tomadas = pandas.concat([tomadas, aux], ignore_index=True)

        i += step

    if tomadas.empty:
        return (ct.reset_index(drop=True), eq.reset_index(drop=True), pandas.DataFrame())

    tomadas["eq_id"] = tomadas["Equipment__c"]
    tomadas["componente_eq_id"] = tomadas["Id"]

    condicoes_tomada = [
        tomadas["Plug_ID__c"] == tomadas["Point_ID__c"],
        tomadas["Plug_ID__c"] == tomadas["Name"],
        tomadas["Name"] == tomadas["Point_ID__c"],
        tomadas["Point_ID__c"].notnull(),
        tomadas["Plug_ID__c"].notnull(),
        tomadas["Name"].notnull()
    ]

    outputs_tomada = [
        tomadas["Plug_ID__c"],
        tomadas["Plug_ID__c"],
        tomadas["Point_ID__c"],
        tomadas["Point_ID__c"],
        tomadas["Plug_ID__c"],
        tomadas["Name"]
    ]

    tomadas["tomada"] = numpy.select(
        condicoes_tomada,
        outputs_tomada,
        default=tomadas["Plug_ID__c"]
    )

    tomadas = pandas.merge(
        left=eq[["salesforce_id", "ct_id", "eq_id"]],
        right=tomadas,
        on="eq_id",
        how="right"
    )

    return (ct.reset_index(drop=True), eq.reset_index(drop=True), tomadas.reset_index(drop=True))


""""|||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||||"""


def obter_informacao_controlotecnico(sf_, lista, origem=None, retirar_duplicados=True):
    i = 0
    step = 25

    ct = pandas.DataFrame()

    while i < len(lista):
        sublista = lista[i:i + step]
        sublista_str = "'" + "', '".join(sublista) + "'"

        query = f"""select Id, Asset__c, Localizacao__c, Instalation_Type__c, Installed_Power_PV_kW__c, Nominal_Power_PV_kW__c, Surroundings_and_Soil__c, Structure_Type__c, Roof_Access__c, Storage__c, Sale_to_the_grid_PV__c, Fixation_Type__c
            from Technical_Control__c
            where Asset__c in ({sublista_str})
            """
        if origem is not None:
            query += f"and Source__c = '{origem}'"
            
        iter = query_salesforce(sf_=sf_, query=query)

        ct = pandas.concat([ct, iter], ignore_index=True)

        i += step
        
    ct = pandas.concat([ct, pandas.json_normalize(ct['Localizacao__c'])], axis=1)
    ct = ct.drop(columns=['Localizacao__c'])

    if retirar_duplicados:
        ct['ranking'] = ct.isnull().sum(axis=1)
        ct.sort_values(by='ranking', ascending=True, inplace=True)
        ct = ct.drop_duplicates(subset=['Asset__c'], keep='first')
        ct = ct.drop(columns=['ranking'])
        
    ct = ct.rename(columns={'Id': 'ct_id', 'Asset__c': 'salesforce_id', 'Instalation_Type__c': 'tipo_instalacao', 'Installed_Power_PV_kW__c': 'peak_power', 'Nominal_Power_PV_kW__c': 'nominal_power', 'Surroundings_and_Soil__c': 'soiling', 'Structure_Type__c': 'tipo_estrutura', 'Roof_Access__c': 'acesso_cobertura', 'Storage__c': 'armazenamento', 'Sale_to_the_grid_PV__c': 'injecao_na_resp', 'Fixation_Type__c': 'tipo_fixacao'})

    return ct


def obter_controlo_licenciamento(sf_, lista):
    obras = obter_informacao_obra_ativo(sf_, lista, retirar_duplicados=False)
    obras = obras[['salesforce_id', 'obra_id']]
    lista_obraid = list(obras.dropna(subset=['obra_id'])['obra_id'].unique())

    tabela, i, step = pandas.DataFrame(), 0, 50

    while i < len(lista_obraid):
        sublista_obraid = lista_obraid[i:i+step]
        sublista_obraid_str = "'" + "', '".join(sublista_obraid) + "'"
        query_contop = f"""select Construction__c, Id from Operational_Control__c where Construction__c in ({sublista_obraid_str})"""
        contop = query_salesforce(sf_, query_contop)
        contop = contop.rename(columns={'Construction__c': 'obra_id', 'Id': 'cont_operacional_id'})

        lista_contopid = list(contop['cont_operacional_id'].unique())
        lista_contopid_str = "'" + "', '".join(lista_contopid) + "'"
        query_contlic = f"""select Controlo_Operacional__c, Id, Name, Licensing_Type_Code__c, Licensing_Status__c, Licensing_Start_Date__c, Licensing_End_Date__c from Licensing_Control__c where Controlo_Operacional__c in ({lista_contopid_str})"""
        contlic = query_salesforce(sf_, query_contlic)
        contlic = contlic.rename(columns={'Controlo_Operacional__c': 'cont_operacional_id', 'Id': 'cont_licenciamento_id', 'Name': 'nome_cont_licenciamento', 'Licensing_Type_Code__c': 'tipo_licenciamento', 'Licensing_Status__c': 'estado_licenciamento', 'Licensing_Start_Date__c': 'data_inicio_lic', 'Licensing_End_Date__c': 'data_fim_lic'})

        iter = pandas.merge(left=contop, right=contlic, on='cont_operacional_id', how='left')
        tabela = pandas.concat([tabela, iter], ignore_index=True)

        i += step
        
    tabela = pandas.merge(left=obras, right=tabela, on='obra_id', how='left')
    
    return tabela


def obter_informacao_obra_ativo(sf_, lista_sf_id, retirar_duplicados=False):
    i = 0
    step = 20

    tabela = pandas.DataFrame()

    while i < len(lista_sf_id):
        sublista = lista_sf_id[i:i + step]
        sublista_str = "'" + "', '".join(sublista) + "'"

        ## Linha de ativos
        aux_asset_line = query_salesforce(sf_=sf_, query=f"select Ativo__c, Construction__c from Asset_Line__c where Ativo__c in ({sublista_str})") # and RecordTypeId = '0123X000000ePmoQAE'
        aux_asset_line = aux_asset_line.rename(columns={'Ativo__c': 'salesforce_id', 'Construction__c': 'obra_id'})

        if aux_asset_line.shape[0] > 0:
            aux_asset_line = aux_asset_line[~aux_asset_line['obra_id'].isnull()].reset_index(drop=True)
            lista_obras = list(aux_asset_line['obra_id'].unique())
            lista_obras = "'" + "', '".join(lista_obras) + "'"

            ## Proposta: retirar dados propriamente ditos
            obra = query_salesforce(sf_=sf_, query=f"select Id, Name, Stage__c, Construction_Current_Status__c, Project_Manager_Team__c, Payment_Conditions__c, Award_Date__c, Product2__c, PGS_PEP__c, Construction_Observations__c from Construction__c where Id in ({lista_obras})")
            obra = obra.rename(columns={'Id': 'obra_id', 'Name': 'nome_obra', 'Stage__c': 'estado_geral', 'Construction_Current_Status__c': 'estado_obra', 'Project_Manager_Team__c': 'standard_customizado', 'Payment_Conditions__c': 'modelo_negocio', 'Award_Date__c': 'data_adjudicacao', 'Product2__c': 'produto_id', 'PGS_PEP__c': 'pep_pgs', 'Construction_Observations__c': 'observacoes_obra'})


            # Juntar tudo
            if aux_asset_line.shape[0] > 0 and obra.shape[0] > 0:
                tabela_iter = pandas.merge(left=aux_asset_line, right=obra, how='left', on='obra_id')
                tabela = pandas.concat([tabela, tabela_iter], ignore_index=True)
            else:
                pass
        else:
            pass

        i += step

    if retirar_duplicados:
        tabela = tabela.drop_duplicates(subset=['salesforce_id'], keep='first')
        
        
    # Converter designação de produto
    lista_produto_id = list(tabela.dropna(subset=['produto_id'])['produto_id'].unique())
    query = f"""select Id, Name from Product2 where Id in ({"'" + "', '".join(lista_produto_id) + "'"})"""
    tabela_dicionario_produto = query_salesforce(sf_, query).rename(columns={'Id': 'produto_id', 'Name': 'produto'})
    
    tabela = pandas.merge(left=tabela, right=tabela_dicionario_produto, on='produto_id', how='left')
    tabela = tabela.drop(columns=['produto_id'])  


    return tabela


def obter_informacao_plano_manutencao(sf_, lista, retirar_pseudo_duplicados=True):
    dados_plano = pandas.DataFrame()

    dicionario_colunas = {'Id': 'plano_id', 'Asset__c': 'salesforce_id', 'Tipo_do_plano_Manutencao__c': 'tipo_plano',
                          'Guarantee_EDP_Type__c': 'tipo_garantia', 'Annual_Update__c': 'atualizacao_anual',
                          'Compensation_Rate__c': 'tarifa_compensacao', 'Warranty_Ceiling__c': 'tecto_garantia',
                          'Guarantee_Value__c': 'valor_garantia',
                          'Warranty_Evaluation_Periodicity__c': 'periodicidade_avaliacao', 'Tipo_de_frequencia__c': 'frequencia_manutencao',
                          'Data_de_In_cio_do_Plano__c': 'data_inicio_plano', 'Data_Fim_do_Plano__c': 'data_fim_plano',
                          'Additional_Information__c': 'informacao_adicional'}

    numero_ativos = len(lista)

    i = 0
    step = 50

    while i < numero_ativos:
        sublista = lista[i:i+step]
        sublista_str = "'" + "', '".join(sublista) + "'"

        query = f"""select Id, Asset__c, Tipo_do_plano_Manutencao__c, Guarantee_EDP_Type__c, Annual_Update__c, 
        Compensation_Rate__c, Warranty_Ceiling__c, Guarantee_Value__c, Warranty_Evaluation_Periodicity__c,
        Tipo_de_frequencia__c, Data_de_In_cio_do_Plano__c, Data_Fim_do_Plano__c, Additional_Information__c
        from Plano_de_Manutencao__c 
        where Asset__c in ({sublista_str})"""

        aux = query_salesforce(sf_, query)
        dados_plano = pandas.concat([dados_plano, aux], ignore_index=True)

        i += step

    dados_plano = dados_plano.rename(columns=dicionario_colunas)

    if retirar_pseudo_duplicados:
        dados_plano['valores_nao_nulos'] = dados_plano.count(axis=1)
        dados_plano = dados_plano.sort_values(by=['valores_nao_nulos'], ascending=False).reset_index(drop=True)
        dados_plano = dados_plano.drop_duplicates(subset=['salesforce_id'], keep='first').reset_index(drop=True)
        dados_plano = dados_plano.drop(columns=['valores_nao_nulos'])

    return dados_plano


def obter_informacao_proposta(sf_, lista, retirar_duplicados=True):
    dados_proposta = pandas.DataFrame()
    numero_ativos = len(lista)

    i = 0
    step = 50

    while i < numero_ativos:
        sublista = lista[i:i + step]
        sublista_str = "'" + "', '".join(sublista) + "'"

        # Dados gerais do ativo
        aux = query_salesforce(sf_=sf_, query=f"select Id, Data_inicio_isencao_reativa__c, DataFimContrato__c, Data_de_transicao__c, Id_Billing_Account__c, Asset_Manager__c, CurrencyIsoCode, Phase__c, Status, Valor_da_Prestacao__c, District__c, Address__c, Product2Id from Asset where Id in ({sublista_str})")

        if aux is None:
            print("erro ao retirar dados de salesforce (datas de exploração, etc.)")
            raise Exception("erro ao retirar dados de salesforce (datas de exploração, etc.)")
        else:
            pass

        # Retirar tipo de share receita, tarifa, etc.
        ## Linha de ativos: correspondência entre ativo e proposta
        aux_asset_line = query_salesforce(sf_=sf_, query=f"select Ativo__c, Proposta__c from Asset_Line__c where Ativo__c in ({sublista_str}) and RecordTypeId = '0123X000000ePmoQAE'")
        aux_asset_line = aux_asset_line.rename(columns={'Ativo__c': 'Id', 'Proposta__c': 'proposta_id'})
        if aux_asset_line.shape[0] > 0:
            aux_asset_line = aux_asset_line[~aux_asset_line['proposta_id'].isnull()].reset_index(drop=True)
            lista_propostas = list(aux_asset_line['proposta_id'].unique())
            lista_propostas = "'" + "', '".join(lista_propostas) + "'"

            ## Proposta: retirar dados propriamente ditos
            aux_proposta = query_salesforce(sf_=sf_, query=f"select Id, QuoteNumber, Condi_es_de_pagamento__c, Revenue_Share_Type__c, Tarifa_MWh__c, CurrencyIsoCode, Update_Rate_Percent_per_Year__c, Dura_o_meses__c, N_de_Mensalidades__c, Valor_da_Presta_o__c, Valor_de_Mensalidade__c, Valor_da_Proposta_Servi_os__c, ExternalID__c, Description from Quote where Id in ({lista_propostas})")
            aux_proposta = aux_proposta.rename(columns={'Id': 'proposta_id',
                                                        'QuoteNumber': 'numero_proposta',
                                                        'Condi_es_de_pagamento__c': 'condicoes_pagamento',
                                                        'Revenue_Share_Type__c': 'tipo_faturacao',
                                                        'Tarifa_MWh__c': 'tarifa_mwh_proposta',
                                                        'CurrencyIsoCode': 'moeda_proposta',
                                                        'Update_Rate_Percent_per_Year__c': 'taxa_atualizacao',
                                                        'Dura_o_meses__c': 'duracao_contrato_meses',
                                                        'N_de_Mensalidades__c': 'num_mensalidades',
                                                        'Valor_da_Presta_o__c': 'valor_prestacao',
                                                        'Valor_de_Mensalidade__c': 'valor_mensalidade',
                                                        'Valor_da_Proposta_Servi_os__c': 'valor_proposta',
                                                        'ExternalID__c': 's2c_id',
                                                        'Description': 'outra_informacao'})

            # Juntar tudo
            tabela_proposta = pandas.merge(left=aux_asset_line, right=aux_proposta, how='left', on='proposta_id')
            aux = pandas.merge(left=aux, right=tabela_proposta, how='left', on='Id').reset_index(drop=True)

            dados_proposta = pandas.concat([dados_proposta, aux], ignore_index=True)
        else:
            pass

        i += step

    # Obter nome e email dos gestores de ativos
    lista_ga = list(dados_proposta.dropna(subset=['Asset_Manager__c'])['Asset_Manager__c'].unique())
    lista_ga_str = "'" + "', '".join(lista_ga) + "'"
    query_ga = f"select Id, Name, Email from User where Id in ({lista_ga_str})"
    aux_ga = query_salesforce(sf_=sf_, query=query_ga)
    aux_ga = aux_ga.rename(columns={'Id': 'Asset_Manager__c', 'Name': 'gestor_ativos', 'Email': 'gestor_ativos_email'})
    dados_proposta = pandas.merge(left=dados_proposta, right=aux_ga, how='left', on='Asset_Manager__c')
    dados_proposta = dados_proposta.drop(columns=['Asset_Manager__c'])

    # Obter nome dos distritos
    lista_distrito_id = list(dados_proposta.dropna(subset=['District__c'])['District__c'].unique())
    lista_distrito_id_str = "'" + "', '".join(lista_distrito_id) + "'"
    query_distrito = f"select Id, Name from Distrito__c where Id in ({lista_distrito_id_str})"
    aux_distrito = query_salesforce(sf_, query_distrito)
    aux_distrito = aux_distrito.rename(columns={'Id': 'District__c', 'Name': 'distrito'})
    dados_proposta = pandas.merge(left=dados_proposta, right=aux_distrito, how='left', on='District__c')
    dados_proposta = dados_proposta.drop(columns=['District__c'])

    dados_proposta['distrito'] = dados_proposta['distrito'].str.lower().str.title()


    # Converter nomes da tabela output
    dicionario_colunas = {'Id': 'salesforce_id', 'Data_inicio_isencao_reativa__c': 'data_inicio_exploracao',
                          'DataFimContrato__c': 'data_fim_exploracao', 'Data_de_transicao__c': 'data_aceitacao_ga',
                          'Phase__c': 'fase', 'Valor_da_Prestacao__c': 'tarifa_mwh_ativo',
                          'CurrencyIsoCode': 'moeda_ativo', 'Status': 'estado', 'District__c': 'distrito',
                          'Address__c': 'morada'}
    dados_proposta = dados_proposta.rename(columns=dicionario_colunas)


    # Obter nome dos produtos
    lista_produto_id = list(dados_proposta.dropna(subset=['Product2Id'])['Product2Id'].unique())
    lista_produto_id_str = "'" + "', '".join(lista_produto_id) + "'"
    query_produto = f"select Id, Name from Product2 where Id in ({lista_produto_id_str})"
    aux_produto = query_salesforce(sf_, query_produto)
    aux_produto = aux_produto.rename(columns={'Id': 'Product2Id', 'Name': 'produto_ativo'})
    dados_proposta = pandas.merge(left=dados_proposta, right=aux_produto, on='Product2Id', how='left')
    dados_proposta = dados_proposta.drop(columns=['Product2Id'])


    # Retirar "duplicados"
    if retirar_duplicados:
        dados_proposta['valores_nao_nulos'] = dados_proposta.count(axis=1)
        dados_proposta = dados_proposta.sort_values(by=['valores_nao_nulos'], ascending=False)
        dados_proposta = dados_proposta.drop_duplicates(subset=['salesforce_id'], keep='first').reset_index(drop=True)

        dados_proposta = dados_proposta.drop(columns=['valores_nao_nulos'])

    return dados_proposta


def obter_pedidos_informacao_operacao_reclamacoes(sf_, lista, periodo):
    inicio, final = periodo[0], periodo[1]
    
    # Obter solicitações
    i = 0
    step = 25

    tabela = pandas.DataFrame()

    while i < len(lista):
        sublista = "'" + "', '".join(lista[i:i+step]) + "'"
        query = f"""select AssetId, Id, Status, RecordTypeId, Origin, Create_Date__c, Closed_Date__c, Incident_type__c, Symptom__c
        from Case
        where AssetId in ({sublista})"""

        aux = query_salesforce(sf_, query)

        tabela = pandas.concat([tabela, aux], ignore_index=True)

        i += step

    tabela = tabela.rename(columns={'Id': 'case_id', 'AssetId': 'salesforce_id', 'Status': 'estado', 'Origin': 'meio', 'Create_Date__c': 'data_abertura', 'Closed_Date__c': 'data_fecho', 'Incident_type__c': 'tipo_incidente', 'Symptom__c': 'sintoma_id'})


    # Ficar com tipos de solicitação pretendidos
    lista_rt = "'" + "', '".join(list(tabela['RecordTypeId'].unique())) + "'"

    query = f"""select Id, Name 
    from RecordType 
    where Id in ({lista_rt})"""

    rt = query_salesforce(sf_, query)
    rt = rt.rename(columns={'Id': 'RecordTypeId', 'Name': 'tipo_solicitacao'})

    tabela = pandas.merge(left=tabela, right=rt, on='RecordTypeId', how='left')
    tabela = tabela.drop(columns=['RecordTypeId'])


    # Filtrar datas
    tabela['data_abertura'] = pandas.to_datetime(tabela['data_abertura']).dt.date
    tabela['data_fecho'] = pandas.to_datetime(tabela['data_fecho']).dt.date

    tabela = tabela[(tabela['data_fecho'] >= inicio) | (tabela['data_fecho'].isnull())]
    tabela = tabela[tabela['data_abertura'] <= final]
    
    tabela_final = pandas.DataFrame(data={'salesforce_id': lista})

    def solicitacoes_recebidas(tabela, x, tipo_solicitacao):
        return tabela[(tabela['tipo_solicitacao'] == tipo_solicitacao) & (tabela['salesforce_id'] == x)].shape[0]
    
    def solicitacoes_abertas(tabela, x, tipo_solicitacao):
        return tabela[(tabela['tipo_solicitacao'] == tipo_solicitacao) & (tabela['salesforce_id'] == x) & (tabela['data_fecho'].isnull())].shape[0]

    tabela_final['pi_recebidos'] = tabela_final['salesforce_id'].apply(lambda x: solicitacoes_recebidas(tabela, x, 'Pedido de Informação'))
    tabela_final['pi_abertos'] = tabela_final['salesforce_id'].apply(lambda x: solicitacoes_abertas(tabela, x, 'Pedido de Informação'))
    tabela_final['po_recebidos'] = tabela_final['salesforce_id'].apply(lambda x: solicitacoes_recebidas(tabela, x, 'Pedido de Operação'))
    tabela_final['po_abertos'] = tabela_final['salesforce_id'].apply(lambda x: solicitacoes_abertas(tabela, x, 'Pedido de Operação'))
    tabela_final['rec_recebidas'] = tabela_final['salesforce_id'].apply(lambda x: solicitacoes_recebidas(tabela, x, 'Reclamação'))
    tabela_final['rec_abertas'] = tabela_final['salesforce_id'].apply(lambda x: solicitacoes_abertas(tabela, x, 'Reclamação'))

    return tabela_final

