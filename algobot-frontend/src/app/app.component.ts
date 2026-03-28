import { Component, inject } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { CommonModule } from '@angular/common';
import { SidebarComponent } from './shared/sidebar/sidebar.component';
import { NavbarComponent } from './shared/navbar/navbar.component';
import { ThemeService } from './core/theme.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, CommonModule, SidebarComponent, NavbarComponent],
  template: `
    <div class="flex h-screen overflow-hidden bg-light-bg dark:bg-dark-bg">

      <app-sidebar
        [collapsed]="sidebarCollapsed"
        (toggleCollapse)="sidebarCollapsed = !sidebarCollapsed">
      </app-sidebar>

      <div class="flex flex-col flex-1 min-w-0 overflow-hidden">
        <app-navbar
          [sidebarCollapsed]="sidebarCollapsed"
          (toggleSidebar)="sidebarCollapsed = !sidebarCollapsed">
        </app-navbar>

        <main class="flex-1 overflow-y-auto p-4 md:p-6 animate-fade-in">
          <router-outlet></router-outlet>
        </main>
      </div>

    </div>
  `,
  styles: [':host { display: block; height: 100vh; }']
})
export class AppComponent {
  theme           = inject(ThemeService);
  sidebarCollapsed = false;
}