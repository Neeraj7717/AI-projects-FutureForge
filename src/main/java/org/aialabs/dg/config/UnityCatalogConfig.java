package org.aialabs.dg.config;

import org.aialabs.dg.CatalogCreation.UnityCatalogManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class UnityCatalogConfig {

    @Bean
    public UnityCatalogManager unityCatalogManager() {
        return new UnityCatalogManager();
    }
}
