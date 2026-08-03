/** @type {import('tailwindcss').Config} */
module.exports = {
	content: ["./blog/**/*.{html,js}", "./admin_scripts/**/*.{html,js}"],
	darkMode: "class",
	theme: {
		extend: {},
	},
	plugins: [require("@tailwindcss/typography")],
};
