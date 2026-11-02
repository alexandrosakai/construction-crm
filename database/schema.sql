-- Esquema do banco de dados (somente estrutura: sem dados, sem INSERT).
-- Uso:  mysql -u root -p -e "CREATE DATABASE app_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
--       mysql -u root -p app_db < database/schema.sql
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE `architects` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int(10) unsigned NOT NULL,
  `razao_social` varchar(255) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_arq_user` (`user_id`),
  CONSTRAINT `fk_arq_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `architecture_survey_responses` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int(10) unsigned DEFAULT NULL,
  `nome` varchar(150) DEFAULT NULL,
  `segmentos` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`segmentos`)),
  `segmentos_outros` varchar(255) DEFAULT NULL,
  `tamanho_projeto` enum('pequeno','medio','grande') DEFAULT NULL,
  `influencias` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`influencias`)),
  `influencias_outros` varchar(255) DEFAULT NULL,
  `sustentabilidade_frequencia` enum('sempre','frequentemente','ocasionalmente','raramente','nunca') DEFAULT NULL,
  `estrategias_sustentaveis` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`estrategias_sustentaveis`)),
  `estrategias_outros` varchar(255) DEFAULT NULL,
  `experiencia_tempo` enum('menos_2','2_5','6_10','mais_10') DEFAULT NULL,
  `tipos_projetos` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`tipos_projetos`)),
  `criterios_escolha` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`criterios_escolha`)),
  `materiais_frequentes` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`materiais_frequentes`)),
  `materiais_outros` text DEFAULT NULL,
  `desafios_especificar` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`desafios_especificar`)),
  `prioriza_sustentavel` enum('sempre','as_vezes','raramente','nunca') DEFAULT NULL,
  `materiais_sustentaveis` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`materiais_sustentaveis`)),
  `materiais_sustentaveis_outros` text DEFAULT NULL,
  `valor_fornecedor` enum('preco','qualidade','suporte','prazo') DEFAULT NULL,
  `teste_materiais` enum('testo_frequentemente','misturo','apenas_consolidadas') DEFAULT NULL,
  `comentarios` text DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT NULL ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_pesq_user` (`user_id`),
  KEY `idx_pesq_created` (`created_at`),
  CONSTRAINT `fk_pesq_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `companies` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `slug` varchar(64) NOT NULL,
  `nome` varchar(120) NOT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `slug` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `employee_survey_responses` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `user_id` bigint(20) NOT NULL,
  `nome` varchar(200) DEFAULT NULL,
  `cargo` varchar(64) DEFAULT NULL,
  `idade` int(11) DEFAULT NULL,
  `telefone` varchar(32) DEFAULT NULL,
  `cep` varchar(16) DEFAULT NULL,
  `rua` varchar(200) DEFAULT NULL,
  `numero` varchar(32) DEFAULT NULL,
  `bairro` varchar(120) DEFAULT NULL,
  `cidade` varchar(120) DEFAULT NULL,
  `estado` varchar(64) DEFAULT NULL,
  `complemento` varchar(200) DEFAULT NULL,
  `lojas_eletrica` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`lojas_eletrica`)),
  `outras_lojas_eletrica` varchar(255) DEFAULT NULL,
  `esportes` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`esportes`)),
  `outros_esportes` varchar(255) DEFAULT NULL,
  `internet` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`internet`)),
  `outros_internet` varchar(255) DEFAULT NULL,
  `tem_instagram` enum('sim','nao') DEFAULT NULL,
  `instagram` varchar(120) DEFAULT NULL,
  `experiencia` enum('1_3','3_5','5_8','8_mais') DEFAULT NULL,
  `projects_simultaneas` enum('1','2','3','4_mais') DEFAULT NULL,
  `tamanho_equipe` enum('1','2_4','5_10','10_mais') DEFAULT NULL,
  `dores` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`dores`)),
  `outras_dores` varchar(255) DEFAULT NULL,
  `tintas` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`tintas`)),
  `outras_tintas` varchar(255) DEFAULT NULL,
  `desejos_loja` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`desejos_loja`)),
  `outros_desejos` varchar(255) DEFAULT NULL,
  `processo_compra` enum('decide','influencia','decide_influencia','apenas_usa') DEFAULT NULL,
  `lojas_preferidas` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`lojas_preferidas`)),
  `outras_lojas` varchar(255) DEFAULT NULL,
  `expectativas_loja` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`expectativas_loja`)),
  `outras_expectativas` varchar(255) DEFAULT NULL,
  `expectativas` text DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `employees` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `user_id` int(10) unsigned NOT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `idx_func_user` (`user_id`),
  CONSTRAINT `fk_func_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

CREATE TABLE `professionals` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `nome` varchar(150) NOT NULL,
  `profissao` varchar(60) NOT NULL,
  `telefone` varchar(11) NOT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `created_by` int(10) unsigned DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_prof_telefone` (`telefone`),
  KEY `idx_prof_profissao` (`profissao`),
  KEY `idx_professionals_dono` (`created_by`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `project_professionals` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `obra_id` bigint(20) unsigned NOT NULL,
  `nome` varchar(120) NOT NULL,
  `cargo` varchar(120) DEFAULT NULL,
  `vinculo` enum('Parceiro Fixo','Contratado por Obra','Fornecedor Eventual') DEFAULT NULL,
  `parceiro` tinyint(1) NOT NULL DEFAULT 0,
  `telefone` varchar(32) DEFAULT NULL,
  `email` varchar(150) DEFAULT NULL,
  `observacoes` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `obra_id` (`obra_id`),
  KEY `nome` (`nome`),
  CONSTRAINT `fk_prof_obra` FOREIGN KEY (`obra_id`) REFERENCES `projects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `project_sales_reps` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `obra_id` bigint(20) unsigned NOT NULL,
  `empresa_id` bigint(20) unsigned NOT NULL,
  `vendedor_id` bigint(20) unsigned DEFAULT NULL,
  `vendedor_nome` varchar(120) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  UNIQUE KEY `uniq_obra_emp_vend` (`obra_id`,`empresa_id`,`vendedor_id`),
  KEY `fk_ov_emp` (`empresa_id`),
  KEY `fk_ov_vend` (`vendedor_id`),
  CONSTRAINT `fk_ov_emp` FOREIGN KEY (`empresa_id`) REFERENCES `companies` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_ov_obra` FOREIGN KEY (`obra_id`) REFERENCES `projects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_ov_vend` FOREIGN KEY (`vendedor_id`) REFERENCES `sales_reps` (`id`) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `project_stages` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `obra_id` bigint(20) unsigned NOT NULL,
  `data_prevista` date NOT NULL,
  `tipo_etapa` enum('projeto','preliminares','fundacao','estrutura','alvenaria','vedacoes','cobertura','impermeabilizacao','instalacoes_hidraulicas','instalacoes_eletricas','instalacoes_gas','revestimentos_internos','revestimentos_externos','forros','esquadrias','vidros','pintura','pisos','bancadas','loucas','climatizacao','paisagismo','limpeza') NOT NULL,
  `observacoes` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `obra_id` (`obra_id`),
  KEY `data_prevista` (`data_prevista`),
  KEY `tipo_etapa` (`tipo_etapa`),
  CONSTRAINT `fk_etp_obra` FOREIGN KEY (`obra_id`) REFERENCES `projects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `project_visits` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `obra_id` bigint(20) unsigned NOT NULL,
  `data_visita` date NOT NULL,
  `responsavel` varchar(120) NOT NULL,
  `contato_nome` varchar(150) DEFAULT NULL,
  `concorrente` varchar(150) DEFAULT NULL,
  `status_obra` enum('iniciada','em_andamento','parada') DEFAULT NULL,
  `estagio_obra` enum('inicial','alvenaria','cobertura','instalacoes','revestimento','acabamento','pintura','concluida') DEFAULT NULL,
  `palavras_chave` text DEFAULT NULL,
  `observacoes` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `obra_id` (`obra_id`),
  KEY `data_visita` (`data_visita`),
  KEY `status_obra` (`status_obra`),
  CONSTRAINT `fk_vis_obra` FOREIGN KEY (`obra_id`) REFERENCES `projects` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `projects` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `numero_obra` bigint(20) unsigned NOT NULL,
  `nome_obra` varchar(255) DEFAULT NULL,
  `endereco_obra` varchar(255) DEFAULT NULL,
  `responsavel_cadastro` varchar(120) NOT NULL,
  `nome` varchar(120) NOT NULL,
  `sobrenome` varchar(120) DEFAULT NULL,
  `logradouro` varchar(200) NOT NULL,
  `numero` varchar(20) NOT NULL,
  `bairro` varchar(120) DEFAULT NULL,
  `cidade` varchar(120) DEFAULT NULL,
  `estado` varchar(60) DEFAULT NULL,
  `cep` varchar(16) NOT NULL,
  `regiao` enum('norte','sul','leste','oeste','centro') DEFAULT NULL,
  `telefone` varchar(20) NOT NULL,
  `email` varchar(150) DEFAULT NULL,
  `cpf` varchar(20) DEFAULT NULL,
  `cnpj` varchar(20) DEFAULT NULL,
  `cliente_pf_pj` enum('cliente_pf','cliente_pj') DEFAULT NULL,
  `latitude` decimal(10,7) DEFAULT NULL,
  `longitude` decimal(10,7) DEFAULT NULL,
  `observacoes` text DEFAULT NULL,
  `tipo_obra` enum('Residencial','Comercial','Industrial','Reforma','Ampliação','Outro') DEFAULT NULL,
  `padrao_obra` enum('muito_alto','alto','medio','baixo') NOT NULL,
  `tipo_cliente` varchar(20) DEFAULT NULL,
  `potencial_obra` enum('Alto Potencial','Médio Potencial','Baixo Potencial','Perdido') DEFAULT NULL,
  `metragem_m2` int(10) unsigned NOT NULL,
  `data_inicio` date DEFAULT NULL,
  `data_termino_prevista` date DEFAULT NULL,
  `favorito` tinyint(1) DEFAULT 0,
  `status` varchar(40) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `created_by` int(10) unsigned DEFAULT NULL,
  `proxima_visita` date DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `numero_obra` (`numero_obra`),
  KEY `numero_obra_2` (`numero_obra`),
  KEY `cep` (`cep`),
  KEY `cidade` (`cidade`),
  KEY `estado` (`estado`),
  KEY `idx_projects_dono` (`created_by`),
  KEY `idx_obras_proxima_visita` (`proxima_visita`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `sales_reps` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `empresa_id` bigint(20) unsigned NOT NULL,
  `nome` varchar(120) NOT NULL,
  `email` varchar(120) DEFAULT NULL,
  `telefone` varchar(32) DEFAULT NULL,
  `ativo` tinyint(1) DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `empresa_id` (`empresa_id`),
  KEY `nome` (`nome`),
  CONSTRAINT `fk_vend_emp` FOREIGN KEY (`empresa_id`) REFERENCES `companies` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `stage_suppliers` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `etapa_id` bigint(20) unsigned NOT NULL,
  `fornecedor_nome` varchar(160) NOT NULL,
  `material` varchar(160) DEFAULT NULL,
  `quantidade` decimal(12,3) DEFAULT NULL,
  `unidade` varchar(20) DEFAULT NULL,
  `preco_unitario` decimal(12,2) DEFAULT NULL,
  `observacoes` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `etapa_id` (`etapa_id`),
  KEY `fornecedor_nome` (`fornecedor_nome`),
  CONSTRAINT `fk_for_etp` FOREIGN KEY (`etapa_id`) REFERENCES `project_stages` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `users` (
  `id` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `username` varchar(100) NOT NULL,
  `password` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `name` varchar(255) DEFAULT NULL,
  `status` varchar(50) DEFAULT 'pendente',
  `categoria` varchar(100) DEFAULT NULL,
  `perfil` varchar(30) DEFAULT NULL,
  `permissoes` text DEFAULT NULL,
  `profile_picture` varchar(255) DEFAULT 'default.png',
  `member_status` varchar(100) DEFAULT 'inativo',
  `telefone` varchar(50) DEFAULT NULL,
  `created_at` datetime DEFAULT current_timestamp(),
  `updated_at` datetime DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  `cidade` varchar(120) DEFAULT NULL,
  `data_nascimento` date DEFAULT NULL,
  `tipo_usuario` enum('arquiteto','funcionario') DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `visit_photos` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `visita_id` bigint(20) unsigned NOT NULL,
  `file_path` varchar(255) NOT NULL,
  `mime_type` varchar(80) DEFAULT NULL,
  `largura_px` int(11) DEFAULT NULL,
  `altura_px` int(11) DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`id`),
  KEY `visita_id` (`visita_id`),
  CONSTRAINT `fk_foto_vis` FOREIGN KEY (`visita_id`) REFERENCES `project_visits` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;
