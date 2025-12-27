"use client";

import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';
import { useAuth } from '@/hooks/useAuth';
import {
  User,
  Bell,
  Shield,
  Palette,
  Database,
  Key,
  Terminal,
  Settings,
  ChevronRight,
  Save,
  Check,
  AlertCircle,
  Moon,
  Sun,
  Monitor,
  Volume2,
  VolumeX,
  Mail,
  Smartphone,
  Lock,
  Eye,
  EyeOff,
  Trash2,
  Download,
  Upload,
  RefreshCw,
  Zap,
  Globe,
  Clock,
  HardDrive,
  Cpu,
  MemoryStick,
  Activity,
} from 'lucide-react';

// Terminal Observatory Theme Constants
const PHOSPHOR_GREEN = '#00ff9f';
const AMBER = '#ffb700';
const CYAN = '#00d4ff';
const CRIMSON = '#ff4757';

// Custom Toggle Switch Component
const ToggleSwitch = ({
  enabled,
  onChange,
  color = PHOSPHOR_GREEN
}: {
  enabled: boolean;
  onChange: (value: boolean) => void;
  color?: string;
}) => (
  <button
    onClick={() => onChange(!enabled)}
    className={cn(
      "relative w-11 h-6 rounded-full transition-all duration-300",
      "border focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0a0a0f]",
      enabled
        ? "border-transparent"
        : "border-white/20 bg-white/5"
    )}
    style={{
      backgroundColor: enabled ? `${color}30` : undefined,
      borderColor: enabled ? color : undefined,
      boxShadow: enabled ? `0 0 12px ${color}40` : undefined,
    }}
  >
    <motion.div
      initial={false}
      animate={{ x: enabled ? 22 : 2 }}
      transition={{ type: "spring", stiffness: 500, damping: 30 }}
      className="absolute top-1 w-4 h-4 rounded-full"
      style={{ backgroundColor: enabled ? color : 'rgba(255,255,255,0.4)' }}
    />
  </button>
);

// Settings Section Component
const SettingsSection = ({
  title,
  icon: Icon,
  children,
  delay = 0,
}: {
  title: string;
  icon: any;
  children: React.ReactNode;
  delay?: number;
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay }}
    className="rounded overflow-hidden border border-white/10 bg-[#0d0d12]"
  >
    {/* Terminal Chrome */}
    <div className="flex items-center gap-1.5 px-3 py-2 border-b border-white/10 bg-white/[0.02]">
      <div className="w-2 h-2 rounded-full bg-red-500/60" />
      <div className="w-2 h-2 rounded-full bg-yellow-500/60" />
      <div className="w-2 h-2 rounded-full bg-green-500/60" />
      <Icon className="w-3.5 h-3.5 text-[#00ff9f] ml-2" />
      <span className="text-[10px] font-mono text-white/40 uppercase tracking-wider">
        {title}
      </span>
    </div>
    <div className="p-5 space-y-4">
      {children}
    </div>
  </motion.div>
);

// Setting Row Component
const SettingRow = ({
  label,
  description,
  children,
}: {
  label: string;
  description?: string;
  children: React.ReactNode;
}) => (
  <div className="flex items-center justify-between gap-4 py-3 border-b border-white/5 last:border-0">
    <div className="flex-1">
      <div className="text-sm font-mono text-white/80">{label}</div>
      {description && (
        <div className="text-xs font-mono text-white/40 mt-0.5">{description}</div>
      )}
    </div>
    <div className="shrink-0">
      {children}
    </div>
  </div>
);

// Navigation Item
const NavItem = ({
  icon: Icon,
  label,
  active,
  onClick,
  color = PHOSPHOR_GREEN,
}: {
  icon: any;
  label: string;
  active: boolean;
  onClick: () => void;
  color?: string;
}) => (
  <button
    onClick={onClick}
    className={cn(
      "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all duration-200",
      "font-mono text-sm text-left",
      active
        ? "text-white"
        : "text-white/50 hover:text-white/70 hover:bg-white/5"
    )}
    style={{
      backgroundColor: active ? `${color}15` : undefined,
      borderLeft: active ? `3px solid ${color}` : '3px solid transparent',
    }}
  >
    <Icon
      className="w-4 h-4 shrink-0"
      style={{ color: active ? color : undefined }}
    />
    <span>{label}</span>
    {active && (
      <ChevronRight className="w-4 h-4 ml-auto" style={{ color }} />
    )}
  </button>
);

export default function SettingsPage() {
  const { user } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [activeSection, setActiveSection] = useState('profile');
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Settings State
  const [settings, setSettings] = useState({
    // Profile
    displayName: '',
    email: '',
    timezone: 'UTC',

    // Appearance
    theme: 'dark',
    accentColor: PHOSPHOR_GREEN,
    crtEffect: true,
    animations: true,
    compactMode: false,

    // Notifications
    emailNotifications: true,
    pushNotifications: false,
    soundEnabled: true,
    documentAlerts: true,
    weeklyDigest: true,

    // Security
    twoFactor: false,
    sessionTimeout: 30,
    showPassword: false,

    // Data
    autoBackup: true,
    backupFrequency: 'daily',
    retentionDays: 30,
  });

  useEffect(() => {
    setMounted(true);
    if (user?.email) {
      setSettings(prev => ({
        ...prev,
        email: user.email || '',
        displayName: user.email?.split('@')[0] || '',
      }));
    }
  }, [user]);

  const handleSave = async () => {
    setIsSaving(true);
    await new Promise(resolve => setTimeout(resolve, 1000));
    setIsSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const sections = [
    { id: 'profile', label: 'Profile', icon: User, color: PHOSPHOR_GREEN },
    { id: 'appearance', label: 'Appearance', icon: Palette, color: CYAN },
    { id: 'notifications', label: 'Notifications', icon: Bell, color: AMBER },
    { id: 'security', label: 'Security', icon: Shield, color: CRIMSON },
    { id: 'data', label: 'Data & Storage', icon: Database, color: PHOSPHOR_GREEN },
    { id: 'system', label: 'System Info', icon: Cpu, color: CYAN },
  ];

  const currentSection = sections.find(s => s.id === activeSection);

  if (!mounted) return null;

  return (
    <div className="min-h-screen bg-[#0a0a0f] relative overflow-hidden">
      {/* CRT Scanlines */}
      <div className="pointer-events-none fixed inset-0 z-50 opacity-[0.03]">
        <div className="h-full w-full" style={{
          backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0, 255, 159, 0.03) 2px, rgba(0, 255, 159, 0.03) 4px)',
        }} />
      </div>

      {/* Background Grid */}
      <div className="absolute inset-0 opacity-[0.02]">
        <div className="h-full w-full" style={{
          backgroundImage: `
            linear-gradient(${PHOSPHOR_GREEN}20 1px, transparent 1px),
            linear-gradient(90deg, ${PHOSPHOR_GREEN}20 1px, transparent 1px)
          `,
          backgroundSize: '50px 50px',
        }} />
      </div>

      {/* Ambient Glows */}
      <div className="absolute top-0 right-1/4 w-[600px] h-[600px] rounded-full blur-[200px] opacity-10"
        style={{ background: `radial-gradient(circle, ${CYAN}, transparent 70%)` }} />
      <div className="absolute bottom-0 left-1/4 w-[500px] h-[500px] rounded-full blur-[150px] opacity-10"
        style={{ background: `radial-gradient(circle, ${PHOSPHOR_GREEN}, transparent 70%)` }} />

      {/* Content */}
      <div className="relative p-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="rounded overflow-hidden border border-white/10 bg-[#0d0d12] mb-6"
        >
          <div className="flex items-center gap-1.5 px-3 py-2 border-b border-white/10 bg-white/[0.02]">
            <div className="w-2 h-2 rounded-full bg-red-500/60" />
            <div className="w-2 h-2 rounded-full bg-yellow-500/60" />
            <div className="w-2 h-2 rounded-full bg-green-500/60" />
            <span className="ml-2 text-[10px] font-mono text-white/30 uppercase tracking-wider">
              System Configuration
            </span>
          </div>

          <div className="p-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg border border-[#00ff9f]/30 bg-gradient-to-br from-[#00ff9f]/20 to-[#00ff9f]/5">
                  <Settings className="w-6 h-6 text-[#00ff9f]" />
                </div>
                <div>
                  <h1 className="text-xl font-mono font-bold text-white/90">Settings</h1>
                  <p className="text-sm font-mono text-white/40">Configure your preferences and system options</p>
                </div>
              </div>

              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleSave}
                disabled={isSaving}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg font-mono text-sm transition-all",
                  "border",
                  saved
                    ? "bg-[#00ff9f]/20 border-[#00ff9f]/50 text-[#00ff9f]"
                    : "bg-[#00ff9f]/10 border-[#00ff9f]/30 text-[#00ff9f] hover:bg-[#00ff9f]/20"
                )}
              >
                {isSaving ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Saving...
                  </>
                ) : saved ? (
                  <>
                    <Check className="w-4 h-4" />
                    Saved!
                  </>
                ) : (
                  <>
                    <Save className="w-4 h-4" />
                    Save Changes
                  </>
                )}
              </motion.button>
            </div>
          </div>
        </motion.div>

        {/* Main Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Sidebar Navigation */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="lg:col-span-1"
          >
            <div className="rounded overflow-hidden border border-white/10 bg-[#0d0d12] sticky top-6">
              <div className="flex items-center gap-1.5 px-3 py-2 border-b border-white/10 bg-white/[0.02]">
                <div className="w-2 h-2 rounded-full bg-red-500/60" />
                <div className="w-2 h-2 rounded-full bg-yellow-500/60" />
                <div className="w-2 h-2 rounded-full bg-green-500/60" />
                <span className="ml-2 text-[10px] font-mono text-white/30 uppercase tracking-wider">
                  Navigation
                </span>
              </div>
              <div className="p-2 space-y-1">
                {sections.map((section) => (
                  <NavItem
                    key={section.id}
                    icon={section.icon}
                    label={section.label}
                    active={activeSection === section.id}
                    onClick={() => setActiveSection(section.id)}
                    color={section.color}
                  />
                ))}
              </div>
            </div>
          </motion.div>

          {/* Settings Content */}
          <div className="lg:col-span-3 space-y-6">
            <AnimatePresence mode="wait">
              {/* Profile Section */}
              {activeSection === 'profile' && (
                <motion.div
                  key="profile"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-6"
                >
                  <SettingsSection title="Profile Information" icon={User} delay={0.2}>
                    <SettingRow label="Display Name" description="Your public display name">
                      <input
                        type="text"
                        value={settings.displayName}
                        onChange={(e) => setSettings(prev => ({ ...prev, displayName: e.target.value }))}
                        className="w-48 px-3 py-1.5 rounded border border-white/10 bg-white/5 font-mono text-sm text-white/80 focus:outline-none focus:border-[#00ff9f]/50"
                        placeholder="Enter name"
                      />
                    </SettingRow>

                    <SettingRow label="Email Address" description="Your account email">
                      <div className="flex items-center gap-2">
                        <Mail className="w-4 h-4 text-white/30" />
                        <span className="font-mono text-sm text-white/60">{settings.email || 'Not set'}</span>
                      </div>
                    </SettingRow>

                    <SettingRow label="Timezone" description="Select your local timezone">
                      <select
                        value={settings.timezone}
                        onChange={(e) => setSettings(prev => ({ ...prev, timezone: e.target.value }))}
                        className="px-3 py-1.5 rounded border border-white/10 bg-white/5 font-mono text-sm text-white/80 focus:outline-none focus:border-[#00ff9f]/50"
                      >
                        <option value="UTC">UTC</option>
                        <option value="EST">Eastern Time</option>
                        <option value="PST">Pacific Time</option>
                        <option value="CET">Central European</option>
                        <option value="JST">Japan Standard</option>
                      </select>
                    </SettingRow>
                  </SettingsSection>

                  <SettingsSection title="Account Status" icon={Activity} delay={0.3}>
                    <div className="grid grid-cols-3 gap-4">
                      {[
                        { label: 'Member Since', value: 'Dec 2024', icon: Clock, color: PHOSPHOR_GREEN },
                        { label: 'Account Type', value: 'Administrator', icon: Shield, color: AMBER },
                        { label: 'API Quota', value: '85% used', icon: Zap, color: CYAN },
                      ].map((stat) => (
                        <div
                          key={stat.label}
                          className="p-4 rounded-lg border border-white/5 bg-white/[0.02]"
                        >
                          <stat.icon className="w-5 h-5 mb-2" style={{ color: stat.color }} />
                          <div className="text-lg font-mono font-bold text-white/90">{stat.value}</div>
                          <div className="text-xs font-mono text-white/40">{stat.label}</div>
                        </div>
                      ))}
                    </div>
                  </SettingsSection>
                </motion.div>
              )}

              {/* Appearance Section */}
              {activeSection === 'appearance' && (
                <motion.div
                  key="appearance"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-6"
                >
                  <SettingsSection title="Theme Settings" icon={Palette} delay={0.2}>
                    <SettingRow label="Color Theme" description="Choose your preferred color scheme">
                      <div className="flex gap-2">
                        {[
                          { value: 'dark', icon: Moon, label: 'Dark' },
                          { value: 'light', icon: Sun, label: 'Light' },
                          { value: 'system', icon: Monitor, label: 'System' },
                        ].map((theme) => (
                          <button
                            key={theme.value}
                            onClick={() => setSettings(prev => ({ ...prev, theme: theme.value }))}
                            className={cn(
                              "flex items-center gap-2 px-3 py-1.5 rounded border font-mono text-xs transition-all",
                              settings.theme === theme.value
                                ? "border-[#00d4ff]/50 bg-[#00d4ff]/10 text-[#00d4ff]"
                                : "border-white/10 bg-white/5 text-white/50 hover:border-white/20"
                            )}
                          >
                            <theme.icon className="w-3.5 h-3.5" />
                            {theme.label}
                          </button>
                        ))}
                      </div>
                    </SettingRow>

                    <SettingRow label="Accent Color" description="Primary accent color for the interface">
                      <div className="flex gap-2">
                        {[
                          { color: PHOSPHOR_GREEN, label: 'Phosphor' },
                          { color: CYAN, label: 'Cyan' },
                          { color: AMBER, label: 'Amber' },
                          { color: '#a855f7', label: 'Purple' },
                        ].map((accent) => (
                          <button
                            key={accent.color}
                            onClick={() => setSettings(prev => ({ ...prev, accentColor: accent.color }))}
                            className={cn(
                              "w-8 h-8 rounded-full border-2 transition-all",
                              settings.accentColor === accent.color
                                ? "border-white scale-110"
                                : "border-transparent hover:scale-105"
                            )}
                            style={{ backgroundColor: accent.color }}
                            title={accent.label}
                          />
                        ))}
                      </div>
                    </SettingRow>

                    <SettingRow label="CRT Scanlines" description="Enable retro CRT effect overlay">
                      <ToggleSwitch
                        enabled={settings.crtEffect}
                        onChange={(val) => setSettings(prev => ({ ...prev, crtEffect: val }))}
                        color={CYAN}
                      />
                    </SettingRow>

                    <SettingRow label="Animations" description="Enable UI animations and transitions">
                      <ToggleSwitch
                        enabled={settings.animations}
                        onChange={(val) => setSettings(prev => ({ ...prev, animations: val }))}
                        color={CYAN}
                      />
                    </SettingRow>

                    <SettingRow label="Compact Mode" description="Reduce spacing for more content density">
                      <ToggleSwitch
                        enabled={settings.compactMode}
                        onChange={(val) => setSettings(prev => ({ ...prev, compactMode: val }))}
                        color={CYAN}
                      />
                    </SettingRow>
                  </SettingsSection>
                </motion.div>
              )}

              {/* Notifications Section */}
              {activeSection === 'notifications' && (
                <motion.div
                  key="notifications"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-6"
                >
                  <SettingsSection title="Notification Preferences" icon={Bell} delay={0.2}>
                    <SettingRow label="Email Notifications" description="Receive updates via email">
                      <ToggleSwitch
                        enabled={settings.emailNotifications}
                        onChange={(val) => setSettings(prev => ({ ...prev, emailNotifications: val }))}
                        color={AMBER}
                      />
                    </SettingRow>

                    <SettingRow label="Push Notifications" description="Browser push notifications">
                      <ToggleSwitch
                        enabled={settings.pushNotifications}
                        onChange={(val) => setSettings(prev => ({ ...prev, pushNotifications: val }))}
                        color={AMBER}
                      />
                    </SettingRow>

                    <SettingRow label="Sound Effects" description="Play sounds for notifications">
                      <div className="flex items-center gap-2">
                        {settings.soundEnabled ? (
                          <Volume2 className="w-4 h-4 text-[#ffb700]" />
                        ) : (
                          <VolumeX className="w-4 h-4 text-white/30" />
                        )}
                        <ToggleSwitch
                          enabled={settings.soundEnabled}
                          onChange={(val) => setSettings(prev => ({ ...prev, soundEnabled: val }))}
                          color={AMBER}
                        />
                      </div>
                    </SettingRow>

                    <SettingRow label="Document Alerts" description="Get notified when documents finish processing">
                      <ToggleSwitch
                        enabled={settings.documentAlerts}
                        onChange={(val) => setSettings(prev => ({ ...prev, documentAlerts: val }))}
                        color={AMBER}
                      />
                    </SettingRow>

                    <SettingRow label="Weekly Digest" description="Receive a weekly summary email">
                      <ToggleSwitch
                        enabled={settings.weeklyDigest}
                        onChange={(val) => setSettings(prev => ({ ...prev, weeklyDigest: val }))}
                        color={AMBER}
                      />
                    </SettingRow>
                  </SettingsSection>
                </motion.div>
              )}

              {/* Security Section */}
              {activeSection === 'security' && (
                <motion.div
                  key="security"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-6"
                >
                  <SettingsSection title="Authentication" icon={Lock} delay={0.2}>
                    <SettingRow label="Two-Factor Authentication" description="Add an extra layer of security">
                      <div className="flex items-center gap-3">
                        {!settings.twoFactor && (
                          <span className="text-xs font-mono text-[#ff4757]">Not enabled</span>
                        )}
                        <ToggleSwitch
                          enabled={settings.twoFactor}
                          onChange={(val) => setSettings(prev => ({ ...prev, twoFactor: val }))}
                          color={CRIMSON}
                        />
                      </div>
                    </SettingRow>

                    <SettingRow label="Session Timeout" description="Auto-logout after inactivity (minutes)">
                      <select
                        value={settings.sessionTimeout}
                        onChange={(e) => setSettings(prev => ({ ...prev, sessionTimeout: parseInt(e.target.value) }))}
                        className="px-3 py-1.5 rounded border border-white/10 bg-white/5 font-mono text-sm text-white/80 focus:outline-none focus:border-[#ff4757]/50"
                      >
                        <option value={15}>15 minutes</option>
                        <option value={30}>30 minutes</option>
                        <option value={60}>1 hour</option>
                        <option value={120}>2 hours</option>
                        <option value={0}>Never</option>
                      </select>
                    </SettingRow>

                    <SettingRow label="Change Password" description="Update your account password">
                      <button className="flex items-center gap-2 px-3 py-1.5 rounded border border-[#ff4757]/30 bg-[#ff4757]/10 text-[#ff4757] font-mono text-xs hover:bg-[#ff4757]/20 transition-colors">
                        <Key className="w-3.5 h-3.5" />
                        Change Password
                      </button>
                    </SettingRow>
                  </SettingsSection>

                  <SettingsSection title="Active Sessions" icon={Globe} delay={0.3}>
                    <div className="space-y-3">
                      {[
                        { device: 'MacBook Pro', location: 'San Francisco, US', time: 'Active now', current: true },
                        { device: 'iPhone 15', location: 'San Francisco, US', time: '2 hours ago', current: false },
                        { device: 'Chrome on Windows', location: 'New York, US', time: '3 days ago', current: false },
                      ].map((session, idx) => (
                        <div
                          key={idx}
                          className={cn(
                            "flex items-center justify-between p-3 rounded-lg border",
                            session.current
                              ? "border-[#00ff9f]/30 bg-[#00ff9f]/5"
                              : "border-white/5 bg-white/[0.02]"
                          )}
                        >
                          <div className="flex items-center gap-3">
                            <div className={cn(
                              "w-2 h-2 rounded-full",
                              session.current ? "bg-[#00ff9f] animate-pulse" : "bg-white/20"
                            )} />
                            <div>
                              <div className="font-mono text-sm text-white/80">{session.device}</div>
                              <div className="font-mono text-xs text-white/40">{session.location} · {session.time}</div>
                            </div>
                          </div>
                          {!session.current && (
                            <button className="text-xs font-mono text-[#ff4757] hover:text-[#ff4757]/80">
                              Revoke
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </SettingsSection>
                </motion.div>
              )}

              {/* Data Section */}
              {activeSection === 'data' && (
                <motion.div
                  key="data"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-6"
                >
                  <SettingsSection title="Backup & Sync" icon={RefreshCw} delay={0.2}>
                    <SettingRow label="Auto Backup" description="Automatically backup your data">
                      <ToggleSwitch
                        enabled={settings.autoBackup}
                        onChange={(val) => setSettings(prev => ({ ...prev, autoBackup: val }))}
                      />
                    </SettingRow>

                    <SettingRow label="Backup Frequency" description="How often to create backups">
                      <select
                        value={settings.backupFrequency}
                        onChange={(e) => setSettings(prev => ({ ...prev, backupFrequency: e.target.value }))}
                        className="px-3 py-1.5 rounded border border-white/10 bg-white/5 font-mono text-sm text-white/80 focus:outline-none focus:border-[#00ff9f]/50"
                      >
                        <option value="hourly">Hourly</option>
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                        <option value="monthly">Monthly</option>
                      </select>
                    </SettingRow>

                    <SettingRow label="Data Retention" description="How long to keep backups">
                      <select
                        value={settings.retentionDays}
                        onChange={(e) => setSettings(prev => ({ ...prev, retentionDays: parseInt(e.target.value) }))}
                        className="px-3 py-1.5 rounded border border-white/10 bg-white/5 font-mono text-sm text-white/80 focus:outline-none focus:border-[#00ff9f]/50"
                      >
                        <option value={7}>7 days</option>
                        <option value={30}>30 days</option>
                        <option value={90}>90 days</option>
                        <option value={365}>1 year</option>
                      </select>
                    </SettingRow>
                  </SettingsSection>

                  <SettingsSection title="Data Management" icon={HardDrive} delay={0.3}>
                    <div className="grid grid-cols-3 gap-4 mb-4">
                      {[
                        { label: 'Documents', value: '2.4 GB', icon: Database, color: PHOSPHOR_GREEN },
                        { label: 'Embeddings', value: '1.2 GB', icon: Cpu, color: CYAN },
                        { label: 'Cache', value: '340 MB', icon: HardDrive, color: AMBER },
                      ].map((storage) => (
                        <div
                          key={storage.label}
                          className="p-4 rounded-lg border border-white/5 bg-white/[0.02]"
                        >
                          <storage.icon className="w-5 h-5 mb-2" style={{ color: storage.color }} />
                          <div className="text-lg font-mono font-bold text-white/90">{storage.value}</div>
                          <div className="text-xs font-mono text-white/40">{storage.label}</div>
                        </div>
                      ))}
                    </div>

                    <div className="flex gap-3">
                      <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[#00ff9f]/30 bg-[#00ff9f]/10 text-[#00ff9f] font-mono text-sm hover:bg-[#00ff9f]/20 transition-colors">
                        <Download className="w-4 h-4" />
                        Export Data
                      </button>
                      <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-white/10 bg-white/5 text-white/60 font-mono text-sm hover:bg-white/10 transition-colors">
                        <Upload className="w-4 h-4" />
                        Import Data
                      </button>
                      <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[#ff4757]/30 bg-[#ff4757]/10 text-[#ff4757] font-mono text-sm hover:bg-[#ff4757]/20 transition-colors">
                        <Trash2 className="w-4 h-4" />
                        Clear Cache
                      </button>
                    </div>
                  </SettingsSection>
                </motion.div>
              )}

              {/* System Info Section */}
              {activeSection === 'system' && (
                <motion.div
                  key="system"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="space-y-6"
                >
                  <SettingsSection title="System Information" icon={Terminal} delay={0.2}>
                    <div className="grid grid-cols-2 gap-4">
                      {[
                        { label: 'Version', value: 'v2.0.0', icon: Terminal },
                        { label: 'Build', value: '2024.12.26', icon: Activity },
                        { label: 'Environment', value: 'Development', icon: Globe },
                        { label: 'API Status', value: 'Online', icon: Zap, status: 'online' },
                      ].map((info) => (
                        <div
                          key={info.label}
                          className="flex items-center gap-3 p-4 rounded-lg border border-white/5 bg-white/[0.02]"
                        >
                          <info.icon className="w-5 h-5 text-[#00ff9f]" />
                          <div>
                            <div className="text-xs font-mono text-white/40">{info.label}</div>
                            <div className="font-mono text-sm text-white/80 flex items-center gap-2">
                              {info.value}
                              {info.status === 'online' && (
                                <span className="w-1.5 h-1.5 rounded-full bg-[#00ff9f] animate-pulse" />
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </SettingsSection>

                  <SettingsSection title="Resource Usage" icon={Activity} delay={0.3}>
                    <div className="space-y-4">
                      {[
                        { label: 'CPU Usage', value: 23, color: PHOSPHOR_GREEN },
                        { label: 'Memory', value: 67, color: AMBER },
                        { label: 'Storage', value: 45, color: CYAN },
                      ].map((resource) => (
                        <div key={resource.label}>
                          <div className="flex items-center justify-between mb-2">
                            <span className="font-mono text-sm text-white/60">{resource.label}</span>
                            <span className="font-mono text-sm text-white/80">{resource.value}%</span>
                          </div>
                          <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                            <motion.div
                              initial={{ width: 0 }}
                              animate={{ width: `${resource.value}%` }}
                              transition={{ duration: 1, delay: 0.3 }}
                              className="h-full rounded-full"
                              style={{ backgroundColor: resource.color }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </SettingsSection>

                  <SettingsSection title="Connected Services" icon={Globe} delay={0.4}>
                    <div className="space-y-3">
                      {[
                        { name: 'PostgreSQL Database', status: 'Connected', latency: '8ms', color: PHOSPHOR_GREEN },
                        { name: 'Vector Store (Qdrant)', status: 'Connected', latency: '15ms', color: PHOSPHOR_GREEN },
                        { name: 'Knowledge Graph (Neo4j)', status: 'Connected', latency: '22ms', color: PHOSPHOR_GREEN },
                        { name: 'Redis Cache', status: 'Connected', latency: '3ms', color: PHOSPHOR_GREEN },
                        { name: 'OpenAI API', status: 'Connected', latency: '156ms', color: AMBER },
                      ].map((service) => (
                        <div
                          key={service.name}
                          className="flex items-center justify-between p-3 rounded-lg border border-white/5 bg-white/[0.02]"
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className="w-2 h-2 rounded-full animate-pulse"
                              style={{ backgroundColor: service.color }}
                            />
                            <span className="font-mono text-sm text-white/70">{service.name}</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span className="font-mono text-xs text-white/40">{service.latency}</span>
                            <span
                              className="font-mono text-xs px-2 py-0.5 rounded"
                              style={{
                                backgroundColor: `${service.color}15`,
                                color: service.color,
                              }}
                            >
                              {service.status}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </SettingsSection>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
