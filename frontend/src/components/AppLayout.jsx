import { AppShell, Burger, Group, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { NavLink, Link } from 'react-router-dom'; // <-- Import Link
import classes from './AppLayout.module.css';

export function AppLayout({ children }) {
  const [opened, { toggle }] = useDisclosure();

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 250, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header withBorder={false} style={{ borderBottom: '1px solid var(--mantine-color-dark-4)' }}>
        <Group h="100%" px="md">
          <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
          
          {/* --- THIS IS THE CHANGE --- */}
          <Link to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
            <Title order={4}>PPT Studio</Title>
          </Link>

        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" style={{ borderRight: '1px solid var(--mantine-color-dark-4)' }}>
        <NavLink to="/enhancer" className={({ isActive }) => isActive ? classes.activeLink : classes.link} onClick={toggle}>
          PPT Enhancer
        </NavLink>
        <NavLink to="/creator" className={({ isActive }) => isActive ? classes.activeLink : classes.link} onClick={toggle}>
          PPT Creator
        </NavLink>
        <NavLink to="/feedback" className={({ isActive }) => isActive ? classes.activeLink : classes.link} onClick={toggle}>
          Feedback
        </NavLink>
      </AppShell.Navbar>

      <AppShell.Main>{children}</AppShell.Main>
    </AppShell>
  );
}